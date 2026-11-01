import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

import store
from lessons import LESSONS, lesson_by_id
from sessions import HostKeyRequired, SessionManager
from tutor import ModelConfig, stream_chat, test_model

manager = SessionManager()
config = ModelConfig()
TOKEN = secrets.token_urlsafe(32)


@asynccontextmanager
async def lifespan(app):
    store.init()
    yield
    await manager.shutdown()


app = FastAPI(title='TermTutor MVP', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]', 'testserver'])


def valid_origin(origin):
    if not origin:
        return True
    parsed = urlsplit(origin)
    return parsed.scheme in ('http', 'https') and parsed.hostname in ('127.0.0.1', 'localhost', '::1', 'testserver')


@app.middleware('http')
async def local_guard(request, call_next):
    if request.url.path.startswith('/api/'):
        if not valid_origin(request.headers.get('origin')) or not secrets.compare_digest(request.headers.get('x-mvp-token', ''), TOKEN):
            return JSONResponse({'detail': '请从本机 TermTutor 页面访问，或刷新页面后重试。'}, status_code=403)
        if int(request.headers.get('content-length', '0') or 0) > 200000:
            return JSONResponse({'detail': '请求内容过大。'}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    if request.url.path == '/':
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; font-src 'self'; frame-ancestors 'none'"
    return response


@app.get('/', response_class=HTMLResponse)
def index():
    return (store.ROOT / 'static' / 'index.html').read_text(encoding='utf-8').replace('__MVP_TOKEN__', TOKEN)


@app.get('/api/health')
def health():
    return {'ok': True, 'model': config.public(), 'active_sessions': sum(not s.closed for s in manager.items.values())}


def get_saved(sid):
    item = store.session(sid)
    if not item:
        raise HTTPException(404, '会话不存在。')
    return item


def get_active(sid):
    get_saved(sid)
    item = manager.items.get(sid)
    if not item or item.closed:
        raise HTTPException(409, '该终端已结束。可查看历史记录，或新建连接继续练习。')
    return item


@app.get('/api/sessions')
def sessions():
    result = store.sessions()
    for item in result:
        active = manager.items.get(item['id'])
        item['connected'] = bool(active and not active.closed)
        item['target'] = active.target if active else '历史会话'
    return result


class SessionInput(BaseModel):
    kind: Literal['local', 'ssh', 'serial'] = 'local'
    label: str = Field(default='', max_length=60)
    host: str = Field(default='', max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(default='', max_length=100)
    password: str = Field(default='', max_length=1000)
    key_path: str = Field(default='', max_length=1000)
    passphrase: str = Field(default='', max_length=1000)
    fingerprint: str = Field(default='', max_length=150)
    device: str = Field(default='', max_length=100)
    baudrate: Literal[9600, 19200, 38400, 57600, 115200, 230400] = 115200


@app.post('/api/sessions')
async def create_session(body: SessionInput):
    if body.kind == 'ssh' and (not body.host.strip() or not body.username.strip()):
        raise HTTPException(422, 'SSH 地址和用户名不能为空。')
    try:
        item = await manager.create(body.model_dump())
        return {'id': item.id, 'kind': item.kind, 'label': item.label, 'connected': True, 'target': item.target}
    except HostKeyRequired as exc:
        return JSONResponse({'detail': str(exc), 'host': exc.host, 'fingerprint': exc.fingerprint,
                             'code': 'HOST_KEY_REQUIRED'}, status_code=409)
    except Exception as exc:
        # Connection errors can contain secrets; expose safe type and a useful generic hint only.
        if isinstance(exc, (ValueError, RuntimeError)):
            detail = str(exc)
        else:
            detail = f'连接失败（{type(exc).__name__}）。请核对地址、认证信息、已知主机密钥或设备占用情况。'
        raise HTTPException(400, detail) from None


@app.delete('/api/sessions/{sid}')
async def close_session(sid: str):
    get_saved(sid)
    item = manager.items.get(sid)
    if item:
        await asyncio.to_thread(item.close)
    return {'ok': True}


@app.get('/api/sessions/{sid}/context')
def context(sid: str):
    get_saved(sid)
    item = manager.items.get(sid)
    return item.inspect() if item else {'session_id': sid, 'connected': False, 'cwd': None, 'target': '历史会话'}


@app.get('/api/sessions/{sid}/messages')
def messages(sid: str):
    get_saved(sid)
    return store.messages(sid)


@app.get('/api/sessions/{sid}/export')
def export(sid: str):
    data = get_saved(sid)
    data['messages'] = store.messages(sid, 10000)
    return JSONResponse(data, headers={'Content-Disposition': f'attachment; filename="termtutor-{sid}.json"'})


@app.get('/api/lessons')
def lessons():
    return LESSONS


class ProgressInput(BaseModel):
    lesson_id: str
    completed: list[int] | None = None


@app.put('/api/sessions/{sid}/progress')
def progress(sid: str, body: ProgressInput):
    item = get_saved(sid)
    lesson = lesson_by_id(body.lesson_id)
    if not lesson:
        raise HTTPException(422, '课程不存在。')
    completed = item['completed']
    if body.completed is not None:
        if any(index < 0 or index >= len(lesson['steps']) for index in body.completed):
            raise HTTPException(422, '步骤编号无效。')
        completed[body.lesson_id] = sorted(set(body.completed))
    store.set_progress(sid, body.lesson_id, completed)
    return store.session(sid)


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    attach_output: bool = True


@app.post('/api/sessions/{sid}/chat')
async def chat(sid: str, body: ChatInput):
    item = get_active(sid)
    if not body.message.strip():
        raise HTTPException(422, '问题不能为空。')
    if item.chat_lock.locked():
        raise HTTPException(409, '当前会话的回答仍在生成，请稍后再试。')
    await item.chat_lock.acquire()

    async def events():
        try:
            async for event in iterate_in_threadpool(stream_chat(item, body.message, body.attach_output, config)):
                yield json.dumps(event, ensure_ascii=False) + '\n'
        finally:
            item.chat_lock.release()
    return StreamingResponse(events(), media_type='application/x-ndjson', headers={'Cache-Control': 'no-store'})


@app.get('/api/model')
def model():
    return config.public()


class ModelInput(BaseModel):
    base_url: str = Field(max_length=1000)
    model: str = Field(max_length=300)
    api_key: str | None = Field(default=None, max_length=2000)
    enabled: bool = True


@app.put('/api/model')
def update_model(body: ModelInput):
    try:
        return config.update(body.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@app.post('/api/model/test')
def check_model():
    try:
        return test_model(config)
    except Exception as exc:
        raise HTTPException(400, f'模型连接检查失败（{type(exc).__name__}），请确认本机服务已启动。') from None


@app.get('/api/serial/ports')
def ports():
    from serial.tools import list_ports
    return [{'device': port.device, 'description': port.description} for port in list_ports.comports()]


@app.get('/api/knowledge')
def knowledge():
    return store.documents()


class DocumentInput(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=60000)


@app.post('/api/knowledge')
def add_document(body: DocumentInput):
    if len(store.documents()) >= 50:
        raise HTTPException(400, 'MVP 最多保存 50 份资料，请先删除不用的导入资料。')
    store.add_document(body.title.strip(), body.content)
    return {'ok': True}


@app.delete('/api/knowledge/{doc_id}')
def delete_document(doc_id: int):
    store.delete_document(doc_id)
    return {'ok': True}


@app.websocket('/ws/{sid}')
async def terminal(websocket: WebSocket, sid: str):
    protocols = [part.strip() for part in websocket.headers.get('sec-websocket-protocol', '').split(',')]
    provided = protocols[1] if len(protocols) == 2 and protocols[0] == 'termtutor' else ''
    if not valid_origin(websocket.headers.get('origin')) or not secrets.compare_digest(provided, TOKEN):
        await websocket.close(code=1008)
        return
    item = manager.items.get(sid)
    if not item or item.closed:
        await websocket.close(code=1008)
        return
    await websocket.accept(subprotocol='termtutor')
    queue = asyncio.Queue(maxsize=256)
    item.subscribers.add(queue)
    sender = None
    try:
        await websocket.send_json({'type': 'output', 'data': item.tail})

        async def send():
            while True:
                event = await queue.get()
                await websocket.send_json(event)
                if event['type'] == 'closed':
                    await websocket.close()
                    return
        sender = asyncio.create_task(send())
        while not item.closed:
            raw = await websocket.receive_text()
            if len(raw) > 70000:
                await websocket.close(code=1009)
                break
            event = json.loads(raw)
            if event.get('type') == 'input':
                data = event.get('data')
                if isinstance(data, str) and len(data) <= 30000:
                    await asyncio.to_thread(item.transport.write, data)
            elif event.get('type') == 'resize':
                cols = max(20, min(400, int(event.get('cols', 100))))
                rows = max(5, min(150, int(event.get('rows', 30))))
                await asyncio.to_thread(item.transport.resize, cols, rows)
    except (WebSocketDisconnect, RuntimeError, OSError, ValueError):
        pass
    finally:
        item.subscribers.discard(queue)
        if sender:
            sender.cancel()


app.mount('/static', StaticFiles(directory=store.ROOT / 'static'), name='static')

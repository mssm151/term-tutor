"""One lightweight end-to-end check. --model additionally calls the configured LLM once."""
import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parent

# Reuse local .env handling without launching the server or embedding an owner's model ID.
import run  # noqa: E402,F401


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', action='store_true', help='Run one real configured-model request')
    parser.add_argument('--model-base-url', default=os.environ.get('MODEL_BASE_URL', 'http://127.0.0.1:1234/v1'))
    parser.add_argument('--model-name', default=os.environ.get('MODEL_NAME', ''))
    args = parser.parse_args()
    if args.model and not args.model_name:
        parser.error('--model needs MODEL_NAME in .env or --model-name')
    (ROOT / 'data').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='smoke-', dir=ROOT / 'data') as directory:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = os.environ.copy()
        env['MVP_DATA_DIR'] = directory
        log_path = Path(directory) / 'server.log'
        with log_path.open('w', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, str(ROOT / 'run.py'), '--port', str(port)],
                                       cwd=ROOT, env=env, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            base = f'http://127.0.0.1:{port}'
            client = requests.Session()
            client.trust_env = False
            sid = None
            try:
                page = None
                for _ in range(100):
                    try:
                        page = client.get(base, timeout=1)
                        if page.status_code == 200:
                            break
                    except requests.ConnectionError:
                        pass
                    if process.poll() is not None:
                        raise RuntimeError(log_path.read_text(encoding='utf-8'))
                    time.sleep(0.1)
                assert page is not None and page.status_code == 200, 'server startup failed'
                token = re.search(r'name="mvp-token" content="([^"]+)"', page.text)[1]
                assert client.post(base + '/api/sessions', json={}).status_code == 403
                client.headers['X-MVP-Token'] = token

                def request(method, path, **kwargs):
                    response = client.request(method, base + '/api' + path, timeout=180 if '/chat' in path else 25, **kwargs)
                    assert response.ok, (path, response.status_code, response.text[:500])
                    return response

                assert request('GET', '/health').json()['ok']
                assert len(request('GET', '/lessons').json()) == 4
                blocked = client.get(base + '/api/sessions', headers={'Origin': 'https://example.com'})
                assert blocked.status_code == 403
                print('PASS startup / API / foreign-origin guard', flush=True)
                data = request('POST', '/sessions', json={'kind': 'local', 'label': 'Smoke terminal'}).json()
                sid = data['id']
                with connect(f'ws://127.0.0.1:{port}/ws/{sid}', subprotocols=['termtutor', token], origin=base, open_timeout=10) as ws:
                    output = ''

                    def receive_until(marker, timeout=20):
                        nonlocal output
                        deadline = time.monotonic() + timeout
                        while marker not in output:
                            assert time.monotonic() < deadline, ('terminal output timeout', output[-1000:])
                            event = json.loads(ws.recv(timeout=max(1, deadline - time.monotonic())))
                            if event['type'] == 'output':
                                output += event['data']

                    receive_until('PS ' if os.name == 'nt' else '$ ')
                    ws.send(json.dumps({'type': 'resize', 'cols': 110, 'rows': 32}))
                    command = "[Console]::WriteLine(('__TT_' + 'OK__'))" if os.name == 'nt' else "printf '__TT_%s__\\n' OK"
                    ws.send(json.dumps({'type': 'input', 'data': command + '\r'}))
                    receive_until('__TT_OK__')
                    if os.name == 'nt':
                        ws.send(json.dumps({'type': 'input', 'data': "New-Item -ItemType Directory -Path smoke-practice | Out-Null\r"}))
                        time.sleep(0.3)
                        ws.send(json.dumps({'type': 'input', 'data': 'Set-Location smoke-practice\r'}))
                        deadline = time.monotonic() + 10
                        while time.monotonic() < deadline:
                            context = request('GET', f'/sessions/{sid}/context').json()
                            if context['cwd'].endswith('smoke-practice'):
                                break
                            time.sleep(0.2)
                        assert context['cwd'].endswith('smoke-practice'), context
                print('PASS real PTY / input-output / resize / current directory tracking', flush=True)
                request('PUT', f'/sessions/{sid}/progress', json={'lesson_id': 'powershell', 'completed': [0]})
                assert request('GET', '/sessions').json()[0]['completed']['powershell'] == [0]
                request('POST', '/knowledge', json={'title': 'Smoke note', 'content': '# Smoke note\n\nsmoke-special-term means a temporary test record.'})
                docs = request('GET', '/knowledge').json()
                imported = next(doc for doc in docs if doc['title'] == 'Smoke note')
                request('DELETE', '/knowledge/' + str(imported['id']))
                request('PUT', '/model', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': '', 'enabled': False})
                response = request('POST', f'/sessions/{sid}/chat', json={'message': 'PowerShell 目录路径怎么理解？'})
                events = [json.loads(line) for line in response.text.splitlines()]
                assert any(event.get('mode') == 'offline' for event in events)
                assert events[-1]['type'] == 'done'
                assert any(event['type'] == 'sources' and event['sources'] for event in events)
                records = request('GET', f'/sessions/{sid}/export').json()
                assert len(records['messages']) == 2
                assert records['completed']['powershell'] == [0]
                print('PASS lessons / knowledge import-delete / offline tutor / persistence-export', flush=True)
                if args.model:
                    request('PUT', '/model', json={'base_url': args.model_base_url, 'model': args.model_name, 'enabled': True})
                    assert request('POST', '/model/test').json()['model_found']
                    started = time.monotonic()
                    response = request('POST', f'/sessions/{sid}/chat', json={'message': '请调用 inspect_environment 工具确认当前本地目录，然后用两句话告诉我 Get-Location 的作用。'})
                    events = [json.loads(line) for line in response.text.splitlines()]
                    errors = [event for event in events if event['type'] == 'error']
                    assert not errors, errors
                    assert events[-1]['type'] == 'done'
                    content = ''.join(event.get('text', '') for event in events if event['type'] == 'delta')
                    assert content.strip(), 'empty model reply'
                    tool_names = [event['name'] for event in events if event['type'] == 'tool' and event['status'] == '完成']
                    print(f'PASS live model streaming ({time.monotonic()-started:.1f}s), tools={tool_names}', flush=True)
                    print('MODEL_REPLY:', content[:600], flush=True)
                request('DELETE', f'/sessions/{sid}')
                assert not request('GET', '/sessions').json()[0]['connected']
                print('PASS terminal close / history retained\nALL SMOKE CHECKS PASSED', flush=True)
            finally:
                if sid:
                    try:
                        client.delete(base + '/api/sessions/' + sid, timeout=5)
                    except requests.RequestException:
                        pass
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == '__main__':
    main()

"""Real terminal transports. Human input is the only source of shell writes."""
import asyncio
import base64
import codecs
import hashlib
import os
import re
import shutil
import socket
import threading
import uuid
from pathlib import Path

import store

ANSI = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]')
CWD = re.compile(r'\x1b\]9;9;([^\x07]*)(?:\x07|\x1b\\)')


def fingerprint(key):
    return 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')


class HostKeyRequired(Exception):
    def __init__(self, host, key):
        self.host = host
        self.fingerprint = fingerprint(key)
        super().__init__('首次连接，请核对服务器主机指纹后重试。')


class LocalTerminal:
    def __init__(self, cwd):
        self.cwd = str(cwd)
        if os.name == 'nt':
            from winpty import PtyProcess
            shell = shutil.which('pwsh')
            if not shell:
                raise RuntimeError('未找到 PowerShell 7 (pwsh)，请安装并加入 PATH。')
            # Prompt emits directory evidence; it does not execute a student's exercise.
            script = 'function global:prompt { [Console]::Write("`e]9;9;$($executionContext.SessionState.Path.CurrentLocation.Path)`a"); "PS $($executionContext.SessionState.Path.CurrentLocation)> " }; Clear-Host'
            encoded = base64.b64encode(script.encode('utf-16le')).decode()
            env = os.environ.copy()
            env.pop('MODEL_API_KEY', None)
            self.process = PtyProcess.spawn([shell, '-NoLogo', '-NoProfile', '-NoExit', '-EncodedCommand', encoded],
                                            cwd=self.cwd, env=env, dimensions=(30, 100))
            self.process.fileobj.settimeout(0.3)
            self.shell = 'PowerShell 7'
        else:
            import fcntl
            import pty
            import struct
            import subprocess
            import termios
            self.master, slave = pty.openpty()
            env = os.environ.copy()
            # Do not pass configured model credentials to the student's shell.
            env.pop('MODEL_API_KEY', None)
            env['TERM'] = 'xterm-256color'
            env['PS1'] = r'\[\e]9;9;\w\a\]\u@\h:\w\$ '
            self.process = subprocess.Popen(['/bin/bash', '--noprofile', '--norc', '-i'], cwd=cwd,
                                            stdin=slave, stdout=slave, stderr=slave, env=env,
                                            start_new_session=True)
            os.close(slave)
            self.shell = 'Bash'
            self.resize(100, 30)

    def read(self):
        if os.name == 'nt':
            return self.process.read(8192)
        import select
        if select.select([self.master], [], [], 0.3)[0]:
            data = os.read(self.master, 8192)
            if not data:
                raise EOFError()
            return data
        if self.process.poll() is not None:
            raise EOFError()
        return b''

    def write(self, data):
        if os.name == 'nt':
            self.process.write(data)
        else:
            os.write(self.master, data.encode())

    def resize(self, cols, rows):
        if os.name == 'nt':
            self.process.setwinsize(rows, cols)
        else:
            import fcntl
            import struct
            import termios
            fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))

    def close(self):
        if os.name == 'nt':
            self.process.close(force=True)
        else:
            import signal
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            os.close(self.master)


class SSHTerminal:
    def __init__(self, config):
        import paramiko
        known_hosts = store.DATA / 'known_hosts'
        accepted = config.get('fingerprint', '')

        class VerifyHostKey(paramiko.MissingHostKeyPolicy):
            def missing_host_key(self, client, hostname, key):
                if not accepted or accepted != fingerprint(key):
                    raise HostKeyRequired(hostname, key)
                client.get_host_keys().add(hostname, key.get_name(), key)
                client.save_host_keys(str(known_hosts))

        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        if known_hosts.exists():
            self.client.load_host_keys(str(known_hosts))
        self.client.set_missing_host_key_policy(VerifyHostKey())
        try:
            self.client.connect(hostname=config['host'], port=config.get('port', 22),
                                username=config['username'], password=config.get('password') or None,
                                key_filename=config.get('key_path') or None,
                                passphrase=config.get('passphrase') or None,
                                look_for_keys=not bool(config.get('password')),
                                allow_agent=True, timeout=10, auth_timeout=12, banner_timeout=10)
            self.channel = self.client.invoke_shell(term='xterm-256color', width=100, height=30)
            self.channel.settimeout(0.3)
            self.shell = '远程 Shell（由目标主机决定）'
            self.client.get_transport().set_keepalive(30)
        except Exception:
            self.client.close()
            raise

    def read(self):
        data = self.channel.recv(8192)
        if not data:
            raise EOFError()
        return data

    def write(self, data):
        self.channel.sendall(data.encode())

    def resize(self, cols, rows):
        self.channel.resize_pty(width=cols, height=rows)

    def close(self):
        self.channel.close()
        self.client.close()


class SerialTerminal:
    def __init__(self, config):
        import serial
        from serial.tools import list_ports
        # Only real, enumerated devices; never permit URL-backed serial transports.
        if config['device'] not in [port.device for port in list_ports.comports()]:
            raise ValueError('串口不存在，请刷新设备列表后选择。')
        self.port = serial.Serial(config['device'], config.get('baudrate', 115200), timeout=0.3,
                                  write_timeout=2, bytesize=8, parity='N', stopbits=1)
        self.shell = '串口文本控制台（8N1 / UTF-8）'

    def read(self):
        return self.port.read(max(1, min(self.port.in_waiting, 8192)))

    def write(self, data):
        self.port.write(data.encode())

    def resize(self, cols, rows):
        pass

    def close(self):
        self.port.close()


class Session:
    def __init__(self, sid, kind, label, transport, loop, target):
        self.id, self.kind, self.label = sid, kind, label
        self.transport, self.loop, self.target = transport, loop, target
        self.cwd = transport.cwd if kind == 'local' else None
        self.tail = ''
        self.closed = False
        self.subscribers = set()
        self.chat_lock = asyncio.Lock()
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.sequence_tail = ''
        self.thread = threading.Thread(target=self._reader, daemon=True, name='terminal-' + sid)
        self.thread.start()

    def _reader(self):
        error = ''
        while not self.closed:
            try:
                data = self.transport.read()
                if isinstance(data, bytes):
                    data = self.decoder.decode(data)
                if data:
                    self.loop.call_soon_threadsafe(self._receive, data)
            except (socket.timeout, TimeoutError):
                continue
            except EOFError:
                break
            except Exception as exc:
                if not self.closed:
                    error = type(exc).__name__
                break
        if not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self._ended, error)

    def _receive(self, data):
        self.tail = (self.tail + data)[-60000:]
        scan = self.sequence_tail + data
        if self.kind == 'local':
            matches = CWD.findall(scan)
            if matches:
                candidate = matches[-1]
                # Only local prompts provide authoritative local cwd evidence.
                if os.path.isabs(candidate) and os.path.isdir(candidate):
                    self.cwd = candidate
        self.sequence_tail = scan[-4096:]
        self._broadcast({'type': 'output', 'data': data})

    def _broadcast(self, event):
        for queue in tuple(self.subscribers):
            if queue.full():
                # A slow/disconnected view must not block the student's process.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait({'type': 'output', 'data': '\r\n[显示较慢，部分输出已略去]\r\n'})
            queue.put_nowait(event)

    def _ended(self, error):
        if not self.closed:
            self.closed = True
            self._broadcast({'type': 'closed', 'error': error})
            try:
                self.transport.close()
            except Exception:
                pass

    def context(self):
        return {'session_id': self.id, 'kind': self.kind, 'target': self.target,
                'shell': self.transport.shell, 'cwd': self.cwd,
                'cwd_note': '本地提示符观测；进入嵌套 SSH/容器后不代表内部环境' if self.kind == 'local' else '未知；不假定继承本机或独立通道目录',
                'connected': not self.closed,
                'terminal_tail': ANSI.sub('', self.tail)[-10000:]}

    def inspect(self):
        data = self.context()
        data.pop('terminal_tail')
        if self.kind == 'local' and self.cwd:
            data['platform'] = os.name
            data['tools'] = {name: bool(shutil.which(name)) for name in ['pwsh', 'ssh', 'docker', 'kubectl', 'git', 'python']}
            try:
                with os.scandir(self.cwd) as entries:
                    data['entries'] = [{'name': entry.name, 'directory': entry.is_dir()} for _, entry in zip(range(30), entries)]
            except OSError as exc:
                data['entries_error'] = str(exc)
        else:
            data['note'] = '远程与串口环境只根据交互终端已有输出分析；未执行额外远程探查。'
        return data

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.transport.close()
            finally:
                self._broadcast({'type': 'closed', 'error': ''})


class SessionManager:
    def __init__(self):
        self.items = {}
        self.creating = 0

    async def create(self, config):
        if sum(not item.closed for item in self.items.values()) + self.creating >= 8:
            raise ValueError('最多同时打开 8 个会话，请先关闭不用的连接。')
        self.creating += 1
        sid = uuid.uuid4().hex[:16]
        kind = config['kind']
        try:
            if kind == 'local':
                workspace = store.DATA / 'workspaces' / sid
                workspace.mkdir(parents=True, exist_ok=True)
                transport = await asyncio.to_thread(LocalTerminal, workspace)
                target = socket.gethostname()
                label = config.get('label') or 'PowerShell' if os.name == 'nt' else config.get('label') or 'Bash'
            elif kind == 'ssh':
                transport = await asyncio.to_thread(SSHTerminal, config)
                target = f"{config['username']}@{config['host']}:{config.get('port', 22)}"
                label = config.get('label') or target
            else:
                transport = await asyncio.to_thread(SerialTerminal, config)
                target = config['device']
                label = config.get('label') or target
            try:
                store.add_session(sid, kind, label)
            except Exception:
                await asyncio.to_thread(transport.close)
                raise
            item = Session(sid, kind, label, transport, asyncio.get_running_loop(), target)
            self.items[sid] = item
            return item
        finally:
            self.creating -= 1

    async def shutdown(self):
        await asyncio.gather(*(asyncio.to_thread(item.close) for item in self.items.values()), return_exceptions=True)

"""Single-machine entry point. Run with the project's Conda Python."""
import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines() if (ROOT / '.env').exists() else []:
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('\"\''))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TermTutor 本地命令行教学工作台')
    parser.add_argument('--port', type=int, default=int(os.environ.get('MVP_PORT', '8765')))
    args = parser.parse_args()
    import uvicorn
    print(f'\nTermTutor → http://127.0.0.1:{args.port}\n按 Ctrl+C 停止。仅监听本机。\n', flush=True)
    uvicorn.run('server:app', host='127.0.0.1', port=args.port, access_log=False)

"""Short serial SSE benchmark; saves metrics only, never keys or generated text."""
import argparse
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests

import run  # Loads local .env without starting the app.

ROOT = Path(__file__).resolve().parent
PROMPT = ('请用中文给命令行初学者写一份 PowerShell 学习笔记。'
          '依次解释当前目录、相对路径、跨盘切换、读取文件、对象管道、报错排查。'
          '每项写清概念、一个命令示例和观察输出的方法，至少写 700 字，不要调用工具。')


def measure(client, base_url, model, headers, max_tokens):
    payload = {'model': model, 'messages': [{'role': 'user', 'content': PROMPT}],
               'stream': True, 'stream_options': {'include_usage': True},
               'temperature': 0, 'max_tokens': max_tokens}
    started = time.perf_counter()
    first = last = None
    usage = None
    finish_reason = None
    chunks = 0
    characters = 0
    completed = False
    with client.post(base_url.rstrip('/') + '/chat/completions', json=payload,
                     headers=headers, stream=True, timeout=(8, 120)) as response:
        if not response.ok:
            raise RuntimeError(f'Model returned HTTP {response.status_code}; no response body saved.')
        for line in response.iter_lines(chunk_size=1):
            if not line.startswith(b'data:'):
                continue
            data = line[5:].strip()
            if data == b'[DONE]':
                completed = True
                break
            event = json.loads(data)
            if event.get('error'):
                raise RuntimeError('Model stream returned an error; no response body saved.')
            if event.get('usage'):
                usage = event['usage']
            for choice in event.get('choices', []):
                text = choice.get('delta', {}).get('content') or ''
                if text:
                    now = time.perf_counter()
                    first = first if first is not None else now
                    last = now
                    characters += len(text)
                    chunks += 1
                if choice.get('finish_reason'):
                    finish_reason = choice['finish_reason']
    ended = time.perf_counter()
    if not completed or first is None or last is None:
        raise RuntimeError('Incomplete model stream or no visible output.')
    if not usage or not isinstance(usage.get('completion_tokens'), int):
        raise RuntimeError('No server completion-token usage: refusing to estimate tokens from characters.')
    count = usage['completion_tokens']
    decode_time = last - first
    result = {
        'prompt_tokens': usage.get('prompt_tokens'), 'completion_tokens': count,
        'visible_characters': characters, 'content_chunks': chunks, 'finish_reason': finish_reason,
        'ttft_seconds': first - started, 'first_to_last_content_seconds': decode_time,
        'total_seconds': ended - started,
        'output_tokens_per_second': (count - 1) / decode_time if count > 1 and decode_time > 0 else None,
        'end_to_end_tokens_per_second': count / (ended - started),
    }
    return {key: round(value, 4) if isinstance(value, float) else value for key, value in result.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=os.environ.get('MODEL_BASE_URL', 'http://127.0.0.1:1234/v1'))
    parser.add_argument('--model', default=os.environ.get('MODEL_NAME', ''))
    parser.add_argument('--runs', type=int, choices=range(1, 6), default=3)
    parser.add_argument('--max-tokens', type=int, choices=range(64, 1025), default=384)
    parser.add_argument('--output', type=Path, default=ROOT / 'data' / 'benchmark-result.json')
    args = parser.parse_args()
    if not args.model:
        parser.error('Configure MODEL_NAME in .env or use --model')
    headers = {}
    key = os.environ.get('MODEL_API_KEY', '')
    if key:
        headers['Authorization'] = 'Bearer ' + key
    report = {
        'measured_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'concurrent_requests_by_this_script': 1, 'warmup_max_tokens': 16,
        'max_tokens_per_sample': args.max_tokens, 'temperature': 0,
        'prompt': PROMPT,
        'method': '(completion_tokens - 1) / (last_visible_content_time - first_visible_content_time)',
        'limitations': ['Client-observed SSE timing, not inference-engine kernel timing.',
                        'A content chunk may contain multiple tokens; the first chunk can affect this estimate.',
                        'Requests are serial; other clients are not controlled. Warm prompt cache may be reused.',
                        'No tool calls or course retrieval; this is not complete application response latency.'],
        'samples': [],
    }
    with requests.Session() as client:
        if urlsplit(args.base_url).hostname in ('127.0.0.1', 'localhost', '::1'):
            client.trust_env = False
        print('Warm-up: one request, up to 16 output tokens.', flush=True)
        measure(client, args.base_url, args.model, headers, 16)
        for index in range(args.runs):
            result = measure(client, args.base_url, args.model, headers, args.max_tokens)
            report['samples'].append(result)
            print(json.dumps({'sample': index + 1, **result}, ensure_ascii=False), flush=True)
    report['summary'] = {
        'median_output_tokens_per_second': round(statistics.median(r['output_tokens_per_second'] for r in report['samples']), 3),
        'median_end_to_end_tokens_per_second': round(statistics.median(r['end_to_end_tokens_per_second'] for r in report['samples']), 3),
        'median_ttft_seconds': round(statistics.median(r['ttft_seconds'] for r in report['samples']), 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SUMMARY', json.dumps(report['summary'], ensure_ascii=False), flush=True)
    print('Metrics saved; model ID, endpoint, generated text and credentials are omitted.', flush=True)


if __name__ == '__main__':
    main()

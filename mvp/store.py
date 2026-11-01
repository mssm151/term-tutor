"""Local SQLite persistence, no terminal transcripts or credentials on disk."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('MVP_DATA_DIR', ROOT / 'data')).resolve()
DB = DATA / 'learning.sqlite3'


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL,
            created_at TEXT NOT NULL, lesson_id TEXT NOT NULL DEFAULT 'powershell',
            completed TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
            role TEXT NOT NULL, content TEXT NOT NULL, mode TEXT NOT NULL,
            sources TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id, id);
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            content TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(source)
        );
        ''')
        for path in sorted((ROOT / 'knowledge').glob('*.md')):
            content = path.read_text(encoding='utf-8')
            title = content.splitlines()[0].lstrip('# ').strip()
            db.execute('''INSERT INTO documents(title,content,source,created_at) VALUES(?,?,?,?)
                ON CONFLICT(source) DO UPDATE SET title=excluded.title,content=excluded.content''',
                       (title, content, '内置资料/' + path.name, now()))


def add_session(sid, kind, label):
    with connect() as db:
        db.execute('INSERT INTO sessions(id,kind,label,created_at) VALUES(?,?,?,?)',
                   (sid, kind, label, now()))


def sessions():
    with connect() as db:
        rows = db.execute('SELECT * FROM sessions ORDER BY created_at DESC LIMIT 100').fetchall()
    return [decode_session(r) for r in rows]


def decode_session(row):
    data = dict(row)
    data['completed'] = json.loads(data['completed'])
    return data


def session(sid):
    with connect() as db:
        row = db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
    return decode_session(row) if row else None


def set_progress(sid, lesson_id, completed):
    with connect() as db:
        db.execute('UPDATE sessions SET lesson_id=?,completed=? WHERE id=?',
                   (lesson_id, json.dumps(completed), sid))


def add_message(sid, role, content, mode, sources=None):
    with connect() as db:
        db.execute('INSERT INTO messages(session_id,role,content,mode,sources,created_at) VALUES(?,?,?,?,?,?)',
                   (sid, role, content, mode, json.dumps(sources or [], ensure_ascii=False), now()))


def messages(sid, limit=80):
    with connect() as db:
        rows = db.execute('SELECT * FROM (SELECT * FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?) ORDER BY id',
                          (sid, limit)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item['sources'] = json.loads(item['sources'])
        result.append(item)
    return result


def documents():
    with connect() as db:
        return [dict(row) for row in db.execute('SELECT id,title,source,length(content) AS size FROM documents ORDER BY id')]


def add_document(title, content):
    source = '本地导入/' + title
    with connect() as db:
        db.execute('''INSERT INTO documents(title,content,source,created_at) VALUES(?,?,?,?)
            ON CONFLICT(source) DO UPDATE SET content=excluded.content,created_at=excluded.created_at''',
                   (title, content, source, now()))


def delete_document(doc_id):
    with connect() as db:
        db.execute("DELETE FROM documents WHERE id=? AND source LIKE '本地导入/%'", (doc_id,))


def search(query, limit=3):
    """Transparent lexical search with Latin terms and CJK bigrams; no model download."""
    import re
    from collections import Counter
    def tokenize(text):
        text = text.lower()
        terms = re.findall(r'[a-z][a-z0-9_-]*', text)
        for segment in re.findall(r'[\u4e00-\u9fff]+', text):
            terms.extend(segment[i:i + 2] for i in range(max(1, len(segment) - 1)))
        return terms
    words = set(tokenize(query))
    if not words:
        return []
    with connect() as db:
        docs = db.execute('SELECT * FROM documents').fetchall()
    found = []
    for doc in docs:
        for ordinal, chunk in enumerate(re.split(r'\n(?=## )', doc['content'])):
            counts = Counter(tokenize(chunk))
            score = sum(min(counts[word], 3) for word in words)
            if score:
                found.append({'id': doc['id'], 'title': doc['title'], 'source': doc['source'],
                              'chunk': ordinal + 1, 'text': chunk[:2200], 'score': score})
    found.sort(key=lambda item: item['score'], reverse=True)
    return found[:limit]

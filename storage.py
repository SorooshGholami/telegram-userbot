"""Lightweight persistence: key/value store plus quick notes.

Operations are tiny, so plain synchronous sqlite3 is used instead of aiosqlite.
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    name    TEXT PRIMARY KEY,
    text    TEXT NOT NULL,
    created INTEGER NOT NULL
);
"""


def init(path: str) -> None:
    global _conn
    _conn = sqlite3.connect(path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.executescript(SCHEMA)
    _conn.commit()


def _db() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("storage.init() was never called.")
    return _conn


# ---------- key/value ----------

def set_key(key: str, value: Any) -> None:
    _db().execute(
        "INSERT INTO kv (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, json.dumps(value, ensure_ascii=False)),
    )
    _db().commit()


def get_key(key: str, default: Any = None) -> Any:
    row = _db().execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def del_key(key: str) -> None:
    _db().execute("DELETE FROM kv WHERE key = ?", (key,))
    _db().commit()


# ---------- notes ----------

def save_note(name: str, text: str) -> None:
    _db().execute(
        "INSERT INTO notes (name, text, created) VALUES (?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET text = excluded.text, created = excluded.created",
        (name.lower(), text, int(time.time())),
    )
    _db().commit()


def get_note(name: str) -> str | None:
    row = _db().execute("SELECT text FROM notes WHERE name = ?", (name.lower(),)).fetchone()
    return row["text"] if row else None


def list_notes() -> list[str]:
    return [r["name"] for r in _db().execute("SELECT name FROM notes ORDER BY name").fetchall()]


def del_note(name: str) -> bool:
    cur = _db().execute("DELETE FROM notes WHERE name = ?", (name.lower(),))
    _db().commit()
    return cur.rowcount > 0

"""SQLite access. One file, WAL, short-lived connections, schema owned here.

Index tables (FTS5 / vec0) are created by the rag slice against this same file.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .config import get_settings

CORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    created_at  REAL NOT NULL,
    finished_at REAL,
    status      TEXT NOT NULL CHECK (status IN ('running','ok','error','cancelled')),
    input       TEXT NOT NULL,
    output      TEXT,
    error       TEXT
);

CREATE TABLE IF NOT EXISTS agent_trace (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id  TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    seq     INTEGER NOT NULL,
    ts      REAL NOT NULL,
    type    TEXT NOT NULL,
    name    TEXT,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trace_run ON agent_trace(run_id, seq);

CREATE TABLE IF NOT EXISTS documents (
    id         TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    title      TEXT,
    media_type TEXT,
    created_at REAL NOT NULL,
    meta       TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS chunks (
    id      TEXT PRIMARY KEY,
    doc_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    page    INTEGER,
    text    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id, ordinal);
"""


def connect() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    with session() as conn:
        conn.executescript(CORE_SCHEMA)


def create_run(run_id: str, payload: dict[str, Any]) -> None:
    with session() as conn:
        conn.execute(
            "INSERT INTO runs (id, created_at, status, input) VALUES (?, ?, 'running', ?)",
            (run_id, time.time(), json.dumps(payload, ensure_ascii=False)),
        )


def finish_run(run_id: str, status: str, output: str | None = None, error: str | None = None) -> None:
    with session() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, finished_at = ?, output = ?, error = ? WHERE id = ?",
            (status, time.time(), output, error, run_id),
        )


def read_trace(run_id: str) -> list[dict[str, Any]]:
    with session() as conn:
        rows = conn.execute(
            "SELECT seq, ts, type, name, payload FROM agent_trace WHERE run_id = ? ORDER BY seq",
            (run_id,),
        ).fetchall()
    return [
        {"seq": r["seq"], "ts": r["ts"], "type": r["type"], "name": r["name"], "data": json.loads(r["payload"])}
        for r in rows
    ]

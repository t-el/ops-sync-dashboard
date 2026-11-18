"""SQLite storage: synced records, run history, and incremental-sync cursors."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS charges (
    id TEXT PRIMARY KEY, amount INTEGER NOT NULL, currency TEXT NOT NULL, status TEXT NOT NULL,
    refunded INTEGER NOT NULL DEFAULT 0, failure_message TEXT, customer_email TEXT, description TEXT,
    created INTEGER NOT NULL, synced_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY, subject TEXT, status TEXT, priority TEXT, requester_email TEXT,
    created_at INTEGER, updated_at INTEGER, synced_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    trigger TEXT NOT NULL,              -- manual | scheduled | retry
    status TEXT NOT NULL,               -- running | success | failed
    attempts INTEGER NOT NULL DEFAULT 0,
    records INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    retry_of INTEGER,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS sync_state (source TEXT PRIMARY KEY, cursor INTEGER);
CREATE INDEX IF NOT EXISTS idx_runs_source ON sync_runs(source, id);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

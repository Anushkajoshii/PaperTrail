"""A small durable job queue in SQLite: the local stand-in for Amazon SQS.

Semantics match what the worker will rely on with SQS:
* at-least-once delivery: a claimed job that is not finished becomes visible again after
  ``visibility_timeout`` seconds (e.g. the worker crashed);
* a job is retried at most ``max_attempts`` times, then marked dead.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Protocol


class JobQueue(Protocol):
    def enqueue(self, check_id: str) -> None: ...
    def claim(self) -> str | None: ...
    def complete(self, check_id: str) -> None: ...
    def fail(self, check_id: str) -> None: ...


class SqliteJobQueue:
    def __init__(
        self,
        path: str | Path,
        *,
        visibility_timeout: float = 900.0,
        max_attempts: int = 3,
        clock=time.time,
    ) -> None:
        self._path = str(path)
        self._timeout = visibility_timeout
        self._max_attempts = max_attempts
        self._clock = clock
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                       check_id TEXT PRIMARY KEY,
                       state TEXT NOT NULL,          -- queued | running | done | dead
                       attempts INTEGER NOT NULL DEFAULT 0,
                       visible_at REAL NOT NULL)"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=30, isolation_level=None)

    def enqueue(self, check_id: str) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO jobs (check_id, state, attempts, visible_at) "
                "VALUES (?, 'queued', 0, ?)",
                (check_id, self._clock()),
            )

    def claim(self) -> str | None:
        """Atomically take the oldest visible job (queued, or running but timed out)."""
        now = self._clock()
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT check_id, attempts FROM jobs WHERE state IN ('queued', 'running') "
                "AND visible_at <= ? ORDER BY visible_at LIMIT 1",
                (now,),
            ).fetchone()
            if row is None:
                db.execute("COMMIT")
                return None
            check_id, attempts = row
            if attempts >= self._max_attempts:
                db.execute("UPDATE jobs SET state = 'dead' WHERE check_id = ?", (check_id,))
                db.execute("COMMIT")
                return self.claim()
            db.execute(
                "UPDATE jobs SET state = 'running', attempts = attempts + 1, visible_at = ? "
                "WHERE check_id = ?",
                (now + self._timeout, check_id),
            )
            db.execute("COMMIT")
            return check_id
        except Exception:
            db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def complete(self, check_id: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE jobs SET state = 'done' WHERE check_id = ?", (check_id,))

    def fail(self, check_id: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE jobs SET state = 'dead' WHERE check_id = ?", (check_id,))

    def state(self, check_id: str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT state FROM jobs WHERE check_id = ?", (check_id,)).fetchone()
        return row[0] if row else None

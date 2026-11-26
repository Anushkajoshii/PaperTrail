"""Where checks are saved. SQLite locally (one file shared by API and worker), DynamoDB later."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from papertrail.models import Check, CheckStatus


class CheckStore(Protocol):
    def save(self, check: Check) -> None: ...
    def get(self, check_id: str) -> Check | None: ...
    def set_status(self, check_id: str, status: CheckStatus, detail: str = "") -> None: ...
    def list_by_creator(self, handle: str, limit: int = 50) -> list[Check]: ...


def _with_status(check: Check, status: CheckStatus, detail: str) -> Check:
    return check.model_copy(
        update={"status": status, "status_detail": detail or None, "updated_at": datetime.now(UTC)}
    )


def normalize_handle(handle: str) -> str:
    return handle.strip().lstrip("@").lower()


class MemoryCheckStore:
    def __init__(self) -> None:
        self._checks: dict[str, Check] = {}
        self._lock = threading.Lock()

    def save(self, check: Check) -> None:
        with self._lock:
            self._checks[check.id] = check

    def get(self, check_id: str) -> Check | None:
        return self._checks.get(check_id)

    def set_status(self, check_id: str, status: CheckStatus, detail: str = "") -> None:
        with self._lock:
            if check_id in self._checks:
                self._checks[check_id] = _with_status(self._checks[check_id], status, detail)

    def list_by_creator(self, handle: str, limit: int = 50) -> list[Check]:
        h = normalize_handle(handle)
        found = [
            c
            for c in self._checks.values()
            if c.input.creator_handle and normalize_handle(c.input.creator_handle) == h
        ]
        return sorted(found, key=lambda c: c.created_at, reverse=True)[:limit]


class SqliteCheckStore:
    """Checks stored as validated JSON. WAL mode lets the API read while the worker writes."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS checks (
                       id TEXT PRIMARY KEY,
                       creator TEXT,
                       status TEXT NOT NULL,
                       created_at TEXT NOT NULL,
                       body TEXT NOT NULL)"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS checks_creator ON checks(creator, created_at)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=30)

    def save(self, check: Check) -> None:
        creator = (
            normalize_handle(check.input.creator_handle) if check.input.creator_handle else None
        )
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO checks (id, creator, status, created_at, body) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    check.id,
                    creator,
                    check.status.value,
                    check.created_at.isoformat(),
                    check.model_dump_json(),
                ),
            )

    def get(self, check_id: str) -> Check | None:
        with self._connect() as db:
            row = db.execute("SELECT body FROM checks WHERE id = ?", (check_id,)).fetchone()
        return Check.model_validate_json(row[0]) if row else None

    def set_status(self, check_id: str, status: CheckStatus, detail: str = "") -> None:
        check = self.get(check_id)
        if check is not None and check.status not in (CheckStatus.COMPLETED, CheckStatus.FAILED):
            self.save(_with_status(check, status, detail))

    def list_by_creator(self, handle: str, limit: int = 50) -> list[Check]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT body FROM checks WHERE creator = ? ORDER BY created_at DESC LIMIT ?",
                (normalize_handle(handle), limit),
            ).fetchall()
        return [Check.model_validate_json(r[0]) for r in rows]


def get_check_store(settings) -> CheckStore:
    if settings.store_backend == "memory":
        return MemoryCheckStore()
    if settings.store_backend == "sqlite":
        return SqliteCheckStore(settings.sqlite_path)
    raise ValueError(f"Unknown store backend '{settings.store_backend}'")

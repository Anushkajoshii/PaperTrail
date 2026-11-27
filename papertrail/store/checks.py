"""Where checks are saved: SQLite locally (one file shared by API and worker), DynamoDB in AWS."""

from __future__ import annotations

import contextlib
import sqlite3
import threading
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from papertrail.models import Check, CheckStatus


class CheckStore(Protocol):
    def save(self, check: Check) -> None: ...
    def get(self, check_id: str) -> Check | None: ...
    def set_status(self, check_id: str, status: CheckStatus, detail: str = "") -> None: ...
    def list_by_creator(self, handle: str, limit: int = 50) -> list[Check]: ...
    def list_recent(self, limit: int = 500) -> list[Check]: ...


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

    def list_recent(self, limit: int = 500) -> list[Check]:
        return sorted(self._checks.values(), key=lambda c: c.created_at, reverse=True)[:limit]


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

    def list_recent(self, limit: int = 500) -> list[Check]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT body FROM checks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Check.model_validate_json(r[0]) for r in rows]


class DynamoDbCheckStore:
    """One item per check. The body is compressed JSON (items are capped at 400 KB).

    ``creator`` is only set when a handle was given, so the ``by_creator`` index stays sparse.
    Items expire automatically after ``retention_days`` (DynamoDB TTL on ``expires_at``).
    """

    FINAL = (CheckStatus.COMPLETED.value, CheckStatus.FAILED.value)

    def __init__(self, table: Any, *, retention_days: int = 180) -> None:
        self._table = table
        self._retention = timedelta(days=retention_days)

    def _item(self, check: Check) -> dict:
        item = {
            "id": check.id,
            "status": check.status.value,
            "created_at": check.created_at.isoformat(),
            "expires_at": int((check.created_at + self._retention).timestamp()),
            "body": zlib.compress(check.model_dump_json().encode("utf-8")),
        }
        if check.input.creator_handle:
            item["creator"] = normalize_handle(check.input.creator_handle)
        return item

    @staticmethod
    def _check(item: dict) -> Check:
        body = item["body"]
        raw = body.value if hasattr(body, "value") else body  # boto3 wraps bytes in Binary
        return Check.model_validate_json(zlib.decompress(bytes(raw)))

    def save(self, check: Check) -> None:
        self._table.put_item(Item=self._item(check))

    def get(self, check_id: str) -> Check | None:
        item = self._table.get_item(Key={"id": check_id}, ConsistentRead=True).get("Item")
        return self._check(item) if item else None

    def set_status(self, check_id: str, status: CheckStatus, detail: str = "") -> None:
        check = self.get(check_id)
        if check is None or check.status.value in self.FINAL:
            return
        done = self._table.meta.client.exceptions.ConditionalCheckFailedException
        # Never overwrite a finished check (the worker may race with a retry).
        with contextlib.suppress(done):
            self._table.put_item(
                Item=self._item(_with_status(check, status, detail)),
                ConditionExpression="#s <> :done AND #s <> :failed",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":done": self.FINAL[0], ":failed": self.FINAL[1]},
            )

    def list_by_creator(self, handle: str, limit: int = 50) -> list[Check]:
        from boto3.dynamodb.conditions import Key

        resp = self._table.query(
            IndexName="by_creator",
            KeyConditionExpression=Key("creator").eq(normalize_handle(handle)),
            ScanIndexForward=False,
            Limit=limit,
        )
        return [self._check(i) for i in resp.get("Items", [])]

    def list_recent(self, limit: int = 500) -> list[Check]:
        """Reads the whole (small) table; meant for occasional reports, not for requests."""
        items: list[dict] = []
        kwargs: dict = {}
        while True:
            page = self._table.scan(**kwargs)
            items.extend(page.get("Items", []))
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        checks = sorted((self._check(i) for i in items), key=lambda c: c.created_at, reverse=True)
        return checks[:limit]


def get_check_store(settings) -> CheckStore:
    if settings.store_backend == "dynamodb":
        if not settings.dynamodb_table:
            raise ValueError("store_backend 'dynamodb' needs PAPERTRAIL_DYNAMODB_TABLE")
        import boto3

        table = boto3.resource("dynamodb", region_name=settings.aws_region).Table(
            settings.dynamodb_table
        )
        return DynamoDbCheckStore(table)
    if settings.store_backend == "memory":
        return MemoryCheckStore()
    if settings.store_backend == "sqlite":
        return SqliteCheckStore(settings.sqlite_path)
    raise ValueError(f"Unknown store backend '{settings.store_backend}'")

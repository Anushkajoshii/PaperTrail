"""Where ledger entries live: memory (tests), SQLite (local) or DynamoDB (AWS)."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Protocol

from papertrail.ledger.models import LedgerEntry, LedgerStatus

ACTIVE = (LedgerStatus.OPEN, LedgerStatus.NO_DATA)


class LedgerStore(Protocol):
    def save(self, entry: LedgerEntry) -> None: ...
    def get(self, entry_id: str) -> LedgerEntry | None: ...
    def list_by_creator(self, creator: str, limit: int = 100) -> list[LedgerEntry]: ...
    def list_active(self) -> list[LedgerEntry]: ...
    def list_recent(self, limit: int = 100) -> list[LedgerEntry]: ...


def _newest_first(entries, limit: int) -> list[LedgerEntry]:
    return sorted(entries, key=lambda e: (e.made_on, e.id), reverse=True)[:limit]


class MemoryLedgerStore:
    def __init__(self) -> None:
        self._entries: dict[str, LedgerEntry] = {}
        self._lock = threading.Lock()

    def save(self, entry: LedgerEntry) -> None:
        with self._lock:
            self._entries[entry.id] = entry

    def get(self, entry_id: str) -> LedgerEntry | None:
        return self._entries.get(entry_id)

    def list_by_creator(self, creator: str, limit: int = 100) -> list[LedgerEntry]:
        return _newest_first((e for e in self._entries.values() if e.creator == creator), limit)

    def list_active(self) -> list[LedgerEntry]:
        return [e for e in self._entries.values() if e.status in ACTIVE]

    def list_recent(self, limit: int = 100) -> list[LedgerEntry]:
        return _newest_first(self._entries.values(), limit)


class SqliteLedgerStore:
    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS ledger (
                       id TEXT PRIMARY KEY, creator TEXT, status TEXT NOT NULL,
                       made_on TEXT NOT NULL, body TEXT NOT NULL)"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS ledger_creator ON ledger(creator, made_on)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=30)

    def save(self, entry: LedgerEntry) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO ledger (id, creator, status, made_on, body) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    entry.id,
                    entry.creator,
                    entry.status.value,
                    entry.made_on.isoformat(),
                    entry.model_dump_json(),
                ),
            )

    def _query(self, sql: str, args: tuple) -> list[LedgerEntry]:
        with self._connect() as db:
            rows = db.execute(sql, args).fetchall()
        return [LedgerEntry.model_validate_json(r[0]) for r in rows]

    def get(self, entry_id: str) -> LedgerEntry | None:
        found = self._query("SELECT body FROM ledger WHERE id = ?", (entry_id,))
        return found[0] if found else None

    def list_by_creator(self, creator: str, limit: int = 100) -> list[LedgerEntry]:
        return self._query(
            "SELECT body FROM ledger WHERE creator = ? ORDER BY made_on DESC, id DESC LIMIT ?",
            (creator, limit),
        )

    def list_active(self) -> list[LedgerEntry]:
        return self._query(
            "SELECT body FROM ledger WHERE status IN (?, ?)", tuple(s.value for s in ACTIVE)
        )

    def list_recent(self, limit: int = 100) -> list[LedgerEntry]:
        return self._query(
            "SELECT body FROM ledger ORDER BY made_on DESC, id DESC LIMIT ?", (limit,)
        )


class DynamoDbLedgerStore:
    """Small table: one item per call, plus a sparse by_creator index."""

    def __init__(self, table: Any) -> None:
        self._table = table

    def save(self, entry: LedgerEntry) -> None:
        item = {
            "id": entry.id,
            "status": entry.status.value,
            "made_on": entry.made_on.isoformat(),
            "body": entry.model_dump_json(),
        }
        if entry.creator:
            item["creator"] = entry.creator
        self._table.put_item(Item=item)

    def get(self, entry_id: str) -> LedgerEntry | None:
        item = self._table.get_item(Key={"id": entry_id}, ConsistentRead=True).get("Item")
        return LedgerEntry.model_validate_json(item["body"]) if item else None

    def list_by_creator(self, creator: str, limit: int = 100) -> list[LedgerEntry]:
        from boto3.dynamodb.conditions import Key

        resp = self._table.query(
            IndexName="by_creator",
            KeyConditionExpression=Key("creator").eq(creator),
            ScanIndexForward=False,
            Limit=limit,
        )
        return [LedgerEntry.model_validate_json(i["body"]) for i in resp.get("Items", [])]

    def _scan(self) -> list[LedgerEntry]:
        items: list[dict] = []
        kwargs: dict = {}
        while True:
            page = self._table.scan(**kwargs)
            items.extend(page.get("Items", []))
            if "LastEvaluatedKey" not in page:
                return [LedgerEntry.model_validate_json(i["body"]) for i in items]
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def list_active(self) -> list[LedgerEntry]:
        return [e for e in self._scan() if e.status in ACTIVE]

    def list_recent(self, limit: int = 100) -> list[LedgerEntry]:
        return _newest_first(self._scan(), limit)


def get_ledger_store(settings) -> LedgerStore:
    if settings.store_backend == "dynamodb":
        if not settings.ledger_table:
            raise ValueError("store_backend 'dynamodb' needs PAPERTRAIL_LEDGER_TABLE")
        import boto3

        resource = boto3.resource("dynamodb", region_name=settings.aws_region)
        return DynamoDbLedgerStore(resource.Table(settings.ledger_table))
    if settings.store_backend == "sqlite":
        return SqliteLedgerStore(settings.sqlite_path)
    return MemoryLedgerStore()

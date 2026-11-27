"""Job queues: Amazon SQS in AWS, and a small durable SQLite queue as its local stand-in.

Semantics match what the worker will rely on with SQS:
* at-least-once delivery: a claimed job that is not finished becomes visible again after
  ``visibility_timeout`` seconds (e.g. the worker crashed);
* a job is retried at most ``max_attempts`` times, then marked dead.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Protocol


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


class SqsJobQueue:
    """Amazon SQS. In AWS the worker Lambda is triggered by the queue, so the API only enqueues.

    ``claim``/``complete`` exist so the same local worker loop can also drain a real queue.
    Failed jobs are retried by SQS and then moved to the dead-letter queue (set in Terraform).
    """

    def __init__(self, sqs_client: Any, queue_url: str) -> None:
        self._sqs, self._url = sqs_client, queue_url
        self._receipts: dict[str, str] = {}

    def enqueue(self, check_id: str) -> None:
        self._sqs.send_message(QueueUrl=self._url, MessageBody=json.dumps({"check_id": check_id}))

    def claim(self) -> str | None:
        msgs = self._sqs.receive_message(QueueUrl=self._url, MaxNumberOfMessages=1).get(
            "Messages", []
        )
        if not msgs:
            return None
        check_id = parse_job(msgs[0]["Body"])
        self._receipts[check_id] = msgs[0]["ReceiptHandle"]
        return check_id

    def complete(self, check_id: str) -> None:
        receipt = self._receipts.pop(check_id, None)
        if receipt:
            self._sqs.delete_message(QueueUrl=self._url, ReceiptHandle=receipt)

    def fail(self, check_id: str) -> None:
        self._receipts.pop(check_id, None)  # SQS redelivers, then dead-letters


def parse_job(body: str) -> str:
    check_id = json.loads(body)["check_id"]
    if not isinstance(check_id, str) or not check_id.startswith("chk_"):
        raise ValueError("Malformed job message")
    return check_id


def get_job_queue(settings) -> JobQueue | None:
    """The queue for the configured mode, or None for inline mode (run in the API process)."""
    if settings.queue_mode == "sqs":
        if not settings.sqs_queue_url:
            raise ValueError("queue_mode 'sqs' needs PAPERTRAIL_SQS_QUEUE_URL")
        import boto3

        return SqsJobQueue(
            boto3.client("sqs", region_name=settings.aws_region), settings.sqs_queue_url
        )
    if settings.queue_mode == "sqlite":
        return SqliteJobQueue(settings.sqlite_path)
    if settings.queue_mode == "inline":
        return None
    raise ValueError(f"Unknown queue mode '{settings.queue_mode}'")

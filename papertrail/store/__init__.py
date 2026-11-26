"""Storage adapters: checks, job queue and uploads.

Each has a small interface with a local implementation now (SQLite / local disk) and an AWS one
later (DynamoDB / SQS / S3 in Part 10), so the API and worker code never change.
"""

from papertrail.store.checks import CheckStore, MemoryCheckStore, SqliteCheckStore, get_check_store
from papertrail.store.queue import JobQueue, SqliteJobQueue
from papertrail.store.uploads import LocalUploadStorage, UploadError, UploadStorage

__all__ = [
    "CheckStore",
    "JobQueue",
    "LocalUploadStorage",
    "MemoryCheckStore",
    "SqliteCheckStore",
    "SqliteJobQueue",
    "UploadError",
    "UploadStorage",
    "get_check_store",
]

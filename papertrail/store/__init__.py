"""Storage adapters: checks, job queue and uploads.

Each has a small interface with a local implementation (SQLite / local disk) and an AWS one
(DynamoDB / SQS / S3), chosen by settings, so the API and worker code never change.
"""

from papertrail.store.checks import (
    CheckStore,
    DynamoDbCheckStore,
    MemoryCheckStore,
    SqliteCheckStore,
    get_check_store,
)
from papertrail.store.queue import JobQueue, SqliteJobQueue, SqsJobQueue, get_job_queue
from papertrail.store.uploads import (
    LocalUploadStorage,
    S3UploadStorage,
    UploadError,
    UploadStorage,
    get_upload_storage,
)

__all__ = [
    "CheckStore",
    "DynamoDbCheckStore",
    "JobQueue",
    "LocalUploadStorage",
    "MemoryCheckStore",
    "S3UploadStorage",
    "SqliteCheckStore",
    "SqliteJobQueue",
    "SqsJobQueue",
    "UploadError",
    "UploadStorage",
    "get_check_store",
    "get_job_queue",
    "get_upload_storage",
]

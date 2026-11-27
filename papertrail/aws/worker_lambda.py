"""SQS-triggered worker Lambda: each message is one check to run.

Reports partial batch failures, so only failed messages go back to the queue (and, after a few
tries, to the dead-letter queue) while finished ones are not repeated.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from papertrail.aws.secrets import load_secrets_from_env
from papertrail.config import get_settings
from papertrail.store import get_check_store, get_upload_storage
from papertrail.store.queue import parse_job
from papertrail.worker import default_deps_factory, process_check

log = logging.getLogger("papertrail.worker")
logging.getLogger().setLevel(logging.INFO)


@lru_cache
def _runtime():
    load_secrets_from_env()
    s = get_settings()
    return get_check_store(s), default_deps_factory(s, get_upload_storage(s))


def handler(event: dict[str, Any], context: Any = None) -> dict[str, list[dict[str, str]]]:
    store, make_deps = _runtime()
    failures: list[dict[str, str]] = []
    for record in event.get("Records", []):
        try:
            check_id = parse_job(record["body"])
        except (KeyError, ValueError):
            log.error("Dropping malformed message %s", record.get("messageId"))
            continue  # retrying a malformed message can never succeed
        try:
            process_check(check_id, store, make_deps)
        except Exception:
            log.exception("Check %s failed; SQS will retry it", check_id)
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}

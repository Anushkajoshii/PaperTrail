"""The worker: takes queued checks, runs the agent, and saves the results.

Locally it polls the SQLite queue (``python -m papertrail.worker``). In AWS the same
``process_check`` function runs inside the SQS-triggered worker Lambda
(``papertrail.aws.worker_lambda``).
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import signal
import threading
import time
from collections.abc import Callable

from papertrail.agent.graph import AgentDeps, run_check
from papertrail.config import Settings, get_settings
from papertrail.ledger.service import track_check
from papertrail.ledger.store import LedgerStore, get_ledger_store
from papertrail.models import Check, CheckStatus
from papertrail.store import (
    CheckStore,
    JobQueue,
    get_check_store,
    get_job_queue,
    get_upload_storage,
)
from papertrail.store.uploads import UploadStorage

log = logging.getLogger("papertrail.worker")

DepsFactory = Callable[..., AgentDeps]


def default_deps_factory(settings: Settings, uploads: UploadStorage) -> DepsFactory:
    def make(**overrides) -> AgentDeps:
        return AgentDeps.from_settings(settings, read_upload=uploads.read_text, **overrides)

    return make


def process_check(
    check_id: str,
    store: CheckStore,
    make_deps: DepsFactory,
    ledger: LedgerStore | None = None,
) -> Check | None:
    """Run one stored check end to end. Progress updates go to the store as they happen.

    Stock calls in a completed check are added to the Claim Ledger (if one is given).
    """
    original = store.get(check_id)
    if original is None:
        log.warning("Check %s not found; skipping", check_id)
        return None
    if original.status in (CheckStatus.COMPLETED, CheckStatus.FAILED):
        return original  # already done (at-least-once delivery can repeat a job)

    def on_progress(status: CheckStatus, detail: str) -> None:
        if status not in (CheckStatus.COMPLETED, CheckStatus.FAILED):
            store.set_status(check_id, status, detail)

    result = run_check(original.input, make_deps(on_progress=on_progress), check_id=check_id)
    final = result.check.model_copy(update={"created_at": original.created_at})
    store.save(final)
    log.info("Check %s finished: %s", check_id, final.status.value)
    if ledger is not None:
        try:
            added = track_check(final, ledger)
            if added:
                log.info("Check %s: %d stock call(s) added to the ledger", check_id, len(added))
        except Exception:  # the fact-check itself is done; the ledger must not undo it
            log.exception("Could not add check %s to the ledger", check_id)
    return final


class Worker:
    def __init__(
        self,
        store: CheckStore,
        queue: JobQueue,
        make_deps: DepsFactory,
        *,
        ledger: LedgerStore | None = None,
        poll_seconds: float = 1.0,
    ) -> None:
        self.store, self.queue, self.make_deps = store, queue, make_deps
        self.ledger = ledger
        self.poll_seconds = poll_seconds
        self.stop_event = threading.Event()

    def run_once(self) -> bool:
        """Process one job if available. Returns True if a job was handled."""
        check_id = self.queue.claim()
        if check_id is None:
            return False
        try:
            process_check(check_id, self.store, self.make_deps, self.ledger)
            self.queue.complete(check_id)
        except Exception:  # keep the worker alive; the job becomes visible again later
            log.exception("Job %s failed; it will be retried", check_id)
        return True

    def run_forever(self) -> None:
        log.info("Worker started")
        while not self.stop_event.is_set():
            if not self.run_once():
                self.stop_event.wait(self.poll_seconds)
        log.info("Worker stopped")


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - exercised via Docker
    parser = argparse.ArgumentParser(description="PaperTrail local worker")
    parser.add_argument("--once", action="store_true", help="Process queued jobs, then exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=get_settings().log_level, format="%(asctime)s %(name)s %(message)s")
    s = get_settings()
    store = get_check_store(s)
    queue = get_job_queue(s)
    if queue is None:
        parser.error("Set PAPERTRAIL_QUEUE_MODE=sqlite (or sqs) to run a separate worker")
    uploads = get_upload_storage(s)
    worker = Worker(store, queue, default_deps_factory(s, uploads), ledger=get_ledger_store(s))
    signal.signal(signal.SIGTERM, lambda *_: worker.stop_event.set())
    if args.once:
        while worker.run_once():
            time.sleep(0)
        return 0
    with contextlib.suppress(KeyboardInterrupt):
        worker.run_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

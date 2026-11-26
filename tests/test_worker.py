from datetime import date
from pathlib import Path

from papertrail.agent.graph import AgentDeps
from papertrail.config import Settings
from papertrail.llm import MockProvider
from papertrail.models import Check, CheckInput, CheckStatus, InputKind
from papertrail.store import LocalUploadStorage, SqliteCheckStore, SqliteJobQueue
from papertrail.tools.search import OfflineSearch
from papertrail.worker import Worker, process_check

EXAMPLES = Path(__file__).parent.parent / "examples"


def factory(uploads=None, seen=None):
    def make(**overrides):
        on_progress = overrides.pop("on_progress", None)

        def record(status, detail):
            if seen is not None:
                seen.append(status)
            if on_progress:
                on_progress(status, detail)

        return AgentDeps(
            provider=MockProvider(),
            search=OfflineSearch(),
            fetcher=None,
            registry=None,
            settings=Settings(_env_file=None),
            today=date(2026, 11, 26),
            read_upload=uploads.read_text if uploads else None,
            on_progress=record,
            **overrides,
        )

    return make


def queued(text=None, **kw):
    inp = kw.pop("input", None) or CheckInput(kind=InputKind.TEXT, text=text)
    return Check(input=inp)


def test_process_check_saves_progress_and_final_result(tmp_path):
    store = SqliteCheckStore(tmp_path / "pt.db")
    check = queued((EXAMPLES / "english_post.txt").read_text())
    store.save(check)
    seen = []
    final = process_check(check.id, store, factory(seen=seen))
    assert final.status is CheckStatus.COMPLETED and final.id == check.id
    assert final.created_at == check.created_at  # creation time preserved
    stored = store.get(check.id)
    assert stored == final and len(stored.verdicts) == 3
    assert CheckStatus.RESEARCHING in seen


def test_process_check_is_idempotent_and_ignores_unknown_ids(tmp_path):
    store = SqliteCheckStore(tmp_path / "pt.db")
    done = queued("Nifty hit 26,277 on 27 September 2024.").model_copy(
        update={"status": CheckStatus.COMPLETED}
    )
    store.save(done)
    assert process_check(done.id, store, factory()) == done
    assert process_check("chk_nope", store, factory()) is None


def test_worker_drains_queue_including_uploaded_subtitles(tmp_path):
    store = SqliteCheckStore(tmp_path / "pt.db")
    queue = SqliteJobQueue(tmp_path / "pt.db")
    uploads = LocalUploadStorage(tmp_path / "uploads")
    key = uploads.save(
        "clip.srt",
        b"1\n00:00:03,000 --> 00:00:06,000\nGuaranteed 10% every month, bilkul risk-free.\n",
    )
    a = queued("Nifty 50 hit an all-time high of 26,277 on 27 September 2024.")
    b = queued(input=CheckInput(kind=InputKind.VIDEO, upload_key=key))
    for c in (a, b):
        store.save(c)
        queue.enqueue(c.id)
    worker = Worker(store, queue, factory(uploads))
    assert worker.run_once() and worker.run_once() and not worker.run_once()
    assert store.get(a.id).status is CheckStatus.COMPLETED
    sub = store.get(b.id)
    assert sub.status is CheckStatus.COMPLETED and sub.claims[0].timestamp_seconds == 3.0
    assert queue.state(a.id) == "done" and queue.state(b.id) == "done"


def test_worker_survives_unexpected_errors(tmp_path):
    store = SqliteCheckStore(tmp_path / "pt.db")
    queue = SqliteJobQueue(tmp_path / "pt.db")
    c = queued("Nifty hit 26,000.")
    store.save(c)
    queue.enqueue(c.id)

    def broken(**_):
        raise RuntimeError("deps unavailable")

    assert Worker(store, queue, broken).run_once() is True
    assert queue.state(c.id) == "running"  # not completed: it becomes visible again later

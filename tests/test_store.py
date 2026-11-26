import threading

import pytest

from papertrail.models import Check, CheckInput, CheckStatus, InputKind
from papertrail.store import (
    LocalUploadStorage,
    MemoryCheckStore,
    SqliteCheckStore,
    SqliteJobQueue,
    UploadError,
)


def new_check(handle=None):
    return Check(
        input=CheckInput(kind=InputKind.TEXT, text="Nifty hit 26,000.", creator_handle=handle)
    )


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    return MemoryCheckStore() if request.param == "memory" else SqliteCheckStore(tmp_path / "t.db")


def test_save_get_and_status(store):
    c = new_check("@DemoCreator")
    store.save(c)
    assert store.get(c.id) == c
    store.set_status(c.id, CheckStatus.RESEARCHING, "round 1")
    got = store.get(c.id)
    assert got.status is CheckStatus.RESEARCHING and got.status_detail == "round 1"
    assert store.get("chk_missing") is None


def test_list_by_creator_normalises_handles(store):
    a, b = new_check("@DemoCreator"), new_check("democreator")
    store.save(a)
    store.save(b)
    store.save(new_check("@someone_else"))
    assert {c.id for c in store.list_by_creator("@democreator")} == {a.id, b.id}


def test_sqlite_does_not_overwrite_finished_checks(tmp_path):
    store = SqliteCheckStore(tmp_path / "t.db")
    c = new_check().model_copy(update={"status": CheckStatus.COMPLETED})
    store.save(c)
    store.set_status(c.id, CheckStatus.JUDGING)  # a late progress event
    assert store.get(c.id).status is CheckStatus.COMPLETED


def test_queue_claim_complete_and_visibility_timeout(tmp_path):
    now = [1000.0]
    q = SqliteJobQueue(
        tmp_path / "q.db", visibility_timeout=60, max_attempts=2, clock=lambda: now[0]
    )
    q.enqueue("chk_a")
    q.enqueue("chk_a")  # duplicate enqueue is ignored
    assert q.claim() == "chk_a" and q.claim() is None  # invisible while running
    now[0] += 61
    assert q.claim() == "chk_a"  # worker "crashed": visible again
    now[0] += 61
    assert q.claim() is None and q.state("chk_a") == "dead"  # max attempts reached
    q.enqueue("chk_b")
    assert q.claim() == "chk_b"
    q.complete("chk_b")
    assert q.state("chk_b") == "done"


def test_queue_claims_each_job_once_under_concurrency(tmp_path):
    q = SqliteJobQueue(tmp_path / "q.db")
    for i in range(20):
        q.enqueue(f"chk_{i}")
    claimed, lock = [], threading.Lock()

    def worker():
        while (job := q.claim()) is not None:
            with lock:
                claimed.append(job)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(claimed) == sorted(f"chk_{i}" for i in range(20))


def test_uploads_are_validated_and_keys_are_safe(tmp_path):
    up = LocalUploadStorage(tmp_path, max_bytes=100)
    key = up.save("My Clip.SRT", b"1\n00:00:01,000 --> 00:00:02,000\nHello\n")
    assert key.startswith("uploads/") and key.endswith(".srt") and "My Clip" not in key
    assert "Hello" in up.read_text(key)
    assert "Hello" in up.read_text("../../etc/" + key.split("/")[-1])  # path parts ignored
    with pytest.raises(UploadError, match="not supported"):
        up.save("evil.exe", b"MZ")
    with pytest.raises(UploadError, match="limit"):
        up.save("big.mp4", b"x" * 101)
    with pytest.raises(UploadError, match="UTF-8"):
        up.save("bad.txt", b"\xff\xfe\x00")
    with pytest.raises(UploadError, match="empty"):
        up.save("empty.vtt", b"")

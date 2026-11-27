from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from papertrail.agent.graph import AgentDeps
from papertrail.api.app import RateLimiter, create_app
from papertrail.config import Settings
from papertrail.llm import MockProvider
from papertrail.store import LocalUploadStorage, MemoryCheckStore, SqliteJobQueue
from papertrail.tools.search import OfflineSearch

EXAMPLES = Path(__file__).parent.parent / "examples"


def make_deps_factory(uploads):
    def make(**overrides):
        return AgentDeps(
            provider=MockProvider(),
            search=OfflineSearch(),
            fetcher=None,
            registry=None,
            settings=Settings(_env_file=None),
            today=date(2026, 11, 26),
            read_upload=uploads.read_text,
            **overrides,
        )

    return make


@pytest.fixture
def api(tmp_path):
    settings = Settings(
        _env_file=None,
        store_backend="memory",
        queue_mode="inline",
        upload_dir=str(tmp_path / "up"),
        rate_limit_per_minute=100,
        max_text_chars=2000,
    )
    store = MemoryCheckStore()
    uploads = LocalUploadStorage(tmp_path / "up", max_bytes=1000)
    app = create_app(settings, store=store, uploads=uploads, make_deps=make_deps_factory(uploads))
    return TestClient(app), store


def test_health_and_security_headers(api):
    client, _ = api
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["llm_provider"] == "mock"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_text_check_end_to_end_inline(api):
    client, _ = api
    r = client.post(
        "/checks",
        json={
            "kind": "text",
            "creator_handle": "@DemoCreator",
            "text": (EXAMPLES / "english_post.txt").read_text(),
        },
    )
    assert r.status_code == 202
    accepted = r.json()
    assert accepted["status"] == "queued" and accepted["status_url"] == f"/checks/{accepted['id']}"
    view = client.get(accepted["status_url"]).json()  # inline task ran after the response
    assert view["is_finished"] and view["progress_percent"] == 100
    check = view["check"]
    assert check["status"] == "completed" and len(check["verdicts"]) == 3
    assert "not financial advice" in " ".join(view["notices"])
    assert view["verdict_descriptions"]["not_verifiable"].endswith("not an accusation.")


def test_creator_page_summarises_checks(api):
    client, _ = api
    for _ in range(2):
        client.post(
            "/checks",
            json={
                "kind": "text",
                "creator_handle": "@demo",
                "text": "Guaranteed 10% every month, risk-free.",
            },
        )
    view = client.get("/creators/DEMO").json()
    assert view["handle"] == "@demo" and view["checks"] == 2
    assert view["totals"]["official_flags"] >= 2 and "not a judgement" in view["note"]
    assert client.get("/creators/nobody").status_code == 404


def test_validation_errors_are_clear(api):
    client, _ = api
    r = client.post("/checks", json={"kind": "text"})
    assert r.status_code == 422 and "requires 'text'" in r.json()["error"]["message"]
    r = client.post("/checks", json={"kind": "video", "text": "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    r = client.post("/checks", json={"kind": "text", "text": "x" * 2001})
    assert r.status_code == 413
    r = client.post("/checks", json={"kind": "article_url", "url": "not a url"})
    assert r.status_code == 422
    assert client.get("/checks/chk_missing").status_code == 404


def test_upload_subtitles_and_bad_files(api):
    client, _ = api
    srt = b"1\n00:00:02,000 --> 00:00:05,000\nGuaranteed 10% every month, bilkul risk-free.\n"
    r = client.post(
        "/checks/upload",
        files={"file": ("clip.srt", srt, "application/x-subrip")},
        data={"creator_handle": "@demo"},
    )
    assert r.status_code == 202
    check = client.get(r.json()["status_url"]).json()["check"]
    assert check["status"] == "completed" and check["claims"][0]["timestamp_seconds"] == 2.0
    txt = client.post("/checks/upload", files={"file": ("post.txt", b"Nifty hit 26,277.")})
    assert txt.status_code == 202
    assert client.post("/checks/upload", files={"file": ("x.exe", b"MZ")}).status_code == 400
    big = client.post("/checks/upload", files={"file": ("a.mp4", b"x" * 2000)})
    assert big.status_code == 413


def test_media_upload_without_aws_fails_gracefully(api):
    client, _ = api
    r = client.post("/checks/upload", files={"file": ("clip.mp3", b"ID3fake", "audio/mpeg")})
    check = client.get(r.json()["status_url"]).json()["check"]
    assert check["status"] == "failed" and ".srt/.vtt/.txt" in check["error"]


def test_reference_endpoints(api):
    client, _ = api
    rb = client.get("/rulebook").json()
    assert len(rb["rules"]) == 7 and all(r["sources"] for r in rb["rules"])
    assert any(s["id"] == "sebi-circular-2025-11-association" for s in rb["sources"])
    terms = {t["term"] for t in client.get("/glossary").json()}
    assert {"Confidence", "Misleading", "Potential concern"} <= terms


def test_sqlite_queue_mode_enqueues_instead_of_running(tmp_path):
    settings = Settings(_env_file=None, store_backend="memory", queue_mode="sqlite")
    queue = SqliteJobQueue(tmp_path / "q.db")
    client = TestClient(
        create_app(
            settings,
            store=MemoryCheckStore(),
            queue=queue,
            uploads=LocalUploadStorage(tmp_path / "up"),
        )
    )
    r = client.post("/checks", json={"kind": "text", "text": "Nifty hit 26,277."})
    assert client.get(r.json()["status_url"]).json()["check"]["status"] == "queued"
    assert queue.claim() == r.json()["id"]


def test_rate_limit(tmp_path):
    limiter = RateLimiter(2)
    assert limiter.allow("ip", 0)[0] and limiter.allow("ip", 1)[0]
    ok, retry = limiter.allow("ip", 2)
    assert not ok and retry > 0
    assert limiter.allow("ip", 61.5)[0]  # window has moved on
    settings = Settings(_env_file=None, store_backend="memory", rate_limit_per_minute=1)
    client = TestClient(
        create_app(
            settings,
            store=MemoryCheckStore(),
            queue=SqliteJobQueue(tmp_path / "q.db"),
            uploads=LocalUploadStorage(tmp_path / "up"),
        )
    )
    body = {"kind": "text", "text": "Nifty hit 26,277."}
    assert client.post("/checks", json=body).status_code == 202
    r = client.post("/checks", json=body)
    assert r.status_code == 429 and "retry-after" in r.headers


def test_openapi_documents_every_route(api):
    client, _ = api
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/checks",
        "/checks/upload",
        "/checks/{check_id}",
        "/creators/{handle}",
        "/rulebook",
        "/glossary",
        "/health",
    } <= set(paths)


def test_lambda_handler_imports(monkeypatch, tmp_path):
    import importlib

    from papertrail.config import get_settings

    monkeypatch.setenv("PAPERTRAIL_STORE_BACKEND", "memory")
    monkeypatch.setenv("PAPERTRAIL_UPLOAD_DIR", str(tmp_path / "up"))
    get_settings.cache_clear()
    try:
        from papertrail.api import lambda_handler

        importlib.reload(lambda_handler)
        assert callable(lambda_handler.handler)
    finally:
        get_settings.cache_clear()


def test_report_endpoint_formats_and_states(api):
    client, _ = api
    r = client.post(
        "/checks",
        json={
            "kind": "text",
            "creator_handle": "@demo",
            "text": (EXAMPLES / "hinglish_reel.txt").read_text(),
        },
    )
    cid = r.json()["id"]
    html = client.get(f"/checks/{cid}/report")
    assert html.status_code == 200 and html.headers["content-type"].startswith("text/html")
    assert "default-src 'none'" in html.headers["content-security-policy"]
    assert "Claims and verdicts" in html.text and "content-disposition" not in html.headers
    md = client.get(f"/checks/{cid}/report?format=md&download=true")
    assert md.headers["content-type"].startswith("text/markdown")
    assert md.headers["content-disposition"] == f'attachment; filename="papertrail-{cid}.md"'
    assert md.text.startswith("# PaperTrail fact-check report")
    printed = client.get(f"/checks/{cid}/report?print=true")
    assert "addEventListener('load'" in printed.text
    assert client.get(f"/checks/{cid}/report?format=pdf").status_code == 422
    assert client.get("/checks/chk_missing/report").status_code == 404


def test_report_not_ready_returns_409(tmp_path):
    settings = Settings(_env_file=None, store_backend="memory", queue_mode="sqlite")
    client = TestClient(
        create_app(
            settings,
            store=MemoryCheckStore(),
            queue=SqliteJobQueue(tmp_path / "q.db"),
            uploads=LocalUploadStorage(tmp_path / "up"),
        )
    )
    cid = client.post("/checks", json={"kind": "text", "text": "Nifty hit 26,277."}).json()["id"]
    r = client.get(f"/checks/{cid}/report")
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_ready"


def test_creator_profile_ledger_timeline_and_compare(api):
    client, _ = api
    for handle, sample in [("@demo", "hinglish_reel.txt"), ("@other", "english_post.txt")]:
        r = client.post(
            "/checks",
            json={
                "kind": "text",
                "creator_handle": handle,
                "text": (EXAMPLES / sample).read_text(),
            },
        )
        assert r.status_code == 202

    p = client.get("/creators/demo").json()
    assert p["handle"] == "@demo" and p["checks"] == 1
    assert p["first_checked"] == p["last_checked"]
    assert p["registration"] == "Not checked"  # no register copy in tests
    tr = p["track_record"]
    assert tr["claims_checked"] >= 3 and tr["enough_data"] is False
    assert tr["supported_share"] is None  # too few claims to show a share
    (call,) = p["ledger"]["entries"]  # TATAMOTORS ka target ₹1500 hai, March tak
    assert call["entry"]["ticker"] == "TATAMOTORS" and call["target"] == 1500
    assert call["entry"]["status"] == "open" and call["entry"]["deadline_stated"] is True
    assert p["ledger"]["counts"]["open"] == 1 and p["ledger"]["hit_share"] is None
    assert p["timeline"] and any(t["official"] for t in p["timeline"])
    assert "not a judgement" in p["note"]

    ledger = client.get("/ledger").json()
    assert [e["entry"]["ticker"] for e in ledger["summary"]["entries"]] == ["TATAMOTORS"]
    assert "first saw them" in ledger["note"]

    cmp = client.get("/creators/compare", params={"handles": ["demo", "@Other", "ghost"]}).json()
    assert [c["handle"] for c in cmp["creators"]] == ["@demo", "@other"]
    assert cmp["missing"] == ["@ghost"] and "not a recommendation" in cmp["note"]
    for bad in (["demo"], ["demo", "@DEMO"], ["a", "b", "c", "d"]):
        assert client.get("/creators/compare", params={"handles": bad}).status_code == 422


def test_stuck_checks_are_shown_as_failed_with_a_clear_message():
    from datetime import UTC, datetime, timedelta

    from papertrail.api.schemas import STALE_AFTER, CheckView
    from papertrail.models import Check, CheckInput, CheckStatus, InputKind

    started = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    running = Check(
        input=CheckInput(kind=InputKind.TEXT, text="x y z"),
        status=CheckStatus.JUDGING,
        updated_at=started,
    )
    fresh = CheckView.of(running, now=started + timedelta(minutes=5))
    assert fresh.check.status is CheckStatus.JUDGING and not fresh.is_finished
    stuck = CheckView.of(running, now=started + STALE_AFTER + timedelta(seconds=1))
    assert stuck.check.status is CheckStatus.FAILED and stuck.is_finished
    assert "free AI service was busy" in stuck.check.error
    done = running.model_copy(update={"status": CheckStatus.QUEUED})
    assert CheckView.of(done, now=started + timedelta(minutes=5)).check.status is CheckStatus.QUEUED

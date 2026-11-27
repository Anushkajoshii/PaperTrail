import asyncio
import json

import httpx
import pytest

pytest.importorskip("mcp")

from mcp.server.mcpserver.exceptions import ToolError

from papertrail.mcp_server import NOTICES, PaperTrailClient, build_server

API = "https://pt.example.test/api"


def done_view(check_id="chk_1"):
    return {
        "status_description": "Done.",
        "check": {
            "id": check_id,
            "status": "completed",
            "detected_language": "hinglish",
            "claims": [
                {"id": "clm_1", "text": "Kestrel rose 40% in 2024.", "quote": "Kestrel 40% upar"},
                {"id": "clm_2", "text": "Main SEBI registered hoon.", "quote": "SEBI registered"},
            ],
            "evidence": [{"id": "evd_1", "title": "Exchange data", "url": "https://x.test/k"}],
            "verdicts": [
                {
                    "claim_id": "clm_1",
                    "label": "supported",
                    "confidence": 0.8,
                    "supporting_evidence_ids": ["evd_1"],
                    "contradicting_evidence_ids": [],
                    "explanation": {"summary": "Exchange data agrees.", "could_not_verify": []},
                }
            ],
            "red_flags": [
                {
                    "basis": "verified_rule",
                    "what_was_detected": "A registration claim",
                    "detected_text": "SEBI registered",
                }
            ],
            "registration": {"status": "not_found"},
        },
    }


def server_with(routes):
    calls = []

    def handler(request: httpx.Request):
        key = f"{request.method} {request.url.path}"
        calls.append((key, request.content))
        body = routes[key]
        body = body() if callable(body) else body
        status = body.pop("_status", 200) if isinstance(body, dict) else 200
        return httpx.Response(status, json=body)

    client = PaperTrailClient(
        API, httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
    )
    return build_server(client), calls


def call(server, name, args):
    """Call a tool the way the MCP protocol layer does; tool errors become RuntimeError here."""
    try:
        result = asyncio.run(server.call_tool(name, args))
    except ToolError as exc:  # sent to the assistant as an error result
        raise RuntimeError(str(exc)) from exc
    return json.loads(result.content[0].text)


def test_check_content_submits_waits_and_summarises():
    views = iter(
        [
            {"check": {"id": "chk_1", "status": "researching"}, "status_description": "Working"},
            done_view(),
        ]
    )
    server, calls = server_with(
        {
            "POST /api/checks": {"id": "chk_1", "status": "queued"},
            "GET /api/checks/chk_1": lambda: next(views),
        }
    )
    out = call(server, "check_content", {"text": "Kestrel 40% upar", "creator_handle": "@demo"})
    assert json.loads(calls[0][1]) == {
        "kind": "text",
        "text": "Kestrel 40% upar",
        "creator_handle": "@demo",
    }
    assert out["claims"][0]["verdict"] == "supported"
    assert out["claims"][0]["sources"] == [{"title": "Exchange data", "url": "https://x.test/k"}]
    assert "verdict" not in out["claims"][1]  # no verdict yet for this claim
    assert out["red_flags"][0]["type"] == "official SEBI flag"
    assert out["result_url"] == "https://pt.example.test/checks/chk_1"
    assert out["report_url"].endswith("/api/checks/chk_1/report") and out["notices"] == NOTICES


def test_running_and_failed_checks():
    server, _ = server_with(
        {"GET /api/checks/chk_2": {"check": {"id": "chk_2", "status": "judging"}}}
    )
    assert "get_check" in call(server, "get_check", {"check_id": "chk_2"})["note"]
    server, _ = server_with(
        {"GET /api/checks/chk_3": {"check": {"id": "chk_3", "status": "failed", "error": "empty"}}}
    )
    assert call(server, "get_check", {"check_id": "chk_3"})["error"] == "empty"


def test_api_errors_are_reported_clearly():
    server, _ = server_with(
        {
            "GET /api/creators/ghost": {
                "_status": 404,
                "error": {"message": "No checks for this creator yet."},
            }
        }
    )
    with pytest.raises(RuntimeError, match="No checks for this creator yet"):
        call(server, "creator_profile", {"handle": "@ghost"})
    with pytest.raises(RuntimeError, match="Give the text"):
        call(server, "check_content", {"text": "  "})


def test_tools_are_listed_with_safety_hints():
    server, _ = server_with({})
    tools = {t.name: t for t in asyncio.run(server.list_tools())}
    assert set(tools) == {
        "check_content",
        "get_check",
        "creator_profile",
        "compare_creators",
        "claim_ledger",
        "sebi_rulebook",
    }
    assert tools["get_check"].annotations.read_only_hint is True
    assert tools["check_content"].annotations.read_only_hint is False

"""PaperTrail as an MCP server: lets AI assistants fact-check finance content with PaperTrail.

Run it (stdio transport, for desktop assistants and IDEs):

    uv run --extra mcp papertrail-mcp

It talks to a PaperTrail API (the live deployment by default; set PAPERTRAIL_API_URL to use a
local one, e.g. http://localhost:8000). Tools return compact, plain data with links back to
the full result, and every answer carries PaperTrail's notices: verdicts are about claims,
not people, and nothing here is financial advice. See docs/MCP.md.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

DEFAULT_API = "https://w5fnwkmfr6.execute-api.ap-southeast-2.amazonaws.com/api"
NOTICES = [
    "PaperTrail assesses specific claims against evidence. It is not financial advice.",
    "Verdicts are about claims, not people. Only SEBI or a court can decide a rule was broken.",
    "SEBI registration does not mean SEBI endorses anyone's advice.",
]
INSTRUCTIONS = (
    "PaperTrail fact-checks what Indian finance creators say (English, Hindi, Hinglish): it "
    "finds checkable claims, weighs evidence, gives a verdict per claim (supported, "
    "contradicted, misleading, not verifiable), and flags statements that official SEBI "
    "material treats as red flags. When you relay results, keep the wording about claims, not "
    "people, mention what could not be verified, and link the full result."
)
FINISHED = {"completed", "failed"}


class PaperTrailClient:
    """Thin client for the PaperTrail HTTP API."""

    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base = (base_url or os.environ.get("PAPERTRAIL_API_URL") or DEFAULT_API).rstrip("/")
        self.site = self.base.removesuffix("/api")
        self._http = client or httpx.Client(timeout=30.0)
        self._sleep = sleep

    def _get(self, path: str, **params: Any) -> dict:
        resp = self._http.get(f"{self.base}{path}", params=params or None)
        return self._json(resp)

    @staticmethod
    def _json(resp: httpx.Response) -> dict:
        if resp.status_code >= 400:
            try:
                message = resp.json()["error"]["message"]
            except Exception:
                message = resp.text[:200]
            raise ToolError(f"PaperTrail API error {resp.status_code}: {message}")
        return resp.json()

    def submit(self, text: str, creator_handle: str | None) -> str:
        body: dict[str, Any] = {"kind": "text", "text": text}
        if creator_handle:
            body["creator_handle"] = creator_handle
        return self._json(self._http.post(f"{self.base}/checks", json=body))["id"]

    def wait(self, check_id: str, timeout_s: float, poll_s: float = 3.0) -> dict:
        waited = 0.0
        while True:
            view = self._get(f"/checks/{check_id}")
            if view["check"]["status"] in FINISHED or waited >= timeout_s:
                return view
            self._sleep(poll_s)
            waited += poll_s


def summarize_check(view: dict, site: str) -> dict:
    """The parts of a check an assistant needs, with links to the full result and report."""
    c = view["check"]
    out: dict[str, Any] = {
        "check_id": c["id"],
        "status": c["status"],
        "status_description": view.get("status_description"),
        "result_url": f"{site}/checks/{c['id']}",
    }
    if c["status"] == "failed":
        return out | {"error": c.get("error")}
    if c["status"] != "completed":
        return out | {"note": "Still running. Call get_check with this check_id in a moment."}
    evidence = {e["id"]: e for e in c.get("evidence", [])}
    verdicts = {v["claim_id"]: v for v in c.get("verdicts", [])}
    claims = []
    for claim in c.get("claims", []):
        v = verdicts.get(claim["id"])
        item: dict[str, Any] = {"claim": claim["text"], "said": claim["quote"]}
        if v:
            cited = [
                *v.get("supporting_evidence_ids", []),
                *v.get("contradicting_evidence_ids", []),
            ]
            item |= {
                "verdict": v["label"],
                "confidence": v["confidence"],
                "summary": v["explanation"]["summary"],
                "could_not_verify": v["explanation"].get("could_not_verify", []),
                "sources": [
                    {"title": evidence[i]["title"], "url": evidence[i]["url"]}
                    for i in cited
                    if i in evidence
                ],
            }
        claims.append(item)
    return out | {
        "language": c.get("detected_language"),
        "claims": claims,
        "red_flags": [
            {
                "type": "official SEBI flag" if f["basis"] == "verified_rule" else "AI concern",
                "what": f["what_was_detected"],
                "said": f["detected_text"],
            }
            for f in c.get("red_flags", [])
        ],
        "sebi_registration": c.get("registration", {}).get("status"),
        "report_url": f"{site}/api/checks/{c['id']}/report",
        "notices": NOTICES,
    }


def build_server(client: PaperTrailClient | None = None) -> MCPServer:
    api = client or PaperTrailClient()
    server = MCPServer(
        "PaperTrail",
        instructions=INSTRUCTIONS,
        website_url=api.site,
    )
    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=True)

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, open_world_hint=True))
    def check_content(text: str, creator_handle: str | None = None, wait_seconds: int = 90) -> dict:
        """Fact-check a finance post, caption or transcript (English, Hindi or Hinglish).

        Submits the text to PaperTrail and waits up to `wait_seconds` (max 240) for verdicts.
        If it is still running, call get_check later with the returned check_id.
        """
        if not text.strip():
            raise ToolError("Give the text to check")
        check_id = api.submit(text, creator_handle)
        view = api.wait(check_id, timeout_s=max(0, min(wait_seconds, 240)))
        return summarize_check(view, api.site)

    @server.tool(annotations=read_only)
    def get_check(check_id: str) -> dict:
        """Get the progress or result of a PaperTrail check by its id (chk_...)."""
        return summarize_check(api._get(f"/checks/{check_id}"), api.site)

    @server.tool(annotations=read_only)
    def creator_profile(handle: str) -> dict:
        """A creator's track record of checked claims, stock calls and red-flag timeline."""
        p = api._get(f"/creators/{handle.lstrip('@')}")
        return {
            "handle": p["handle"],
            "checks": p["checks"],
            "sebi_registration": p["registration"],
            "track_record": p["track_record"],
            "stock_calls": p["ledger"]["counts"],
            "recent_red_flags": [
                {"date": t["date"], "official": t["official"], "what": t["what"]}
                for t in p["timeline"][:10]
            ],
            "profile_url": f"{api.site}/creators/{p['handle'].lstrip('@')}",
            "note": p["note"],
        }

    @server.tool(annotations=read_only)
    def compare_creators(handles: list[str]) -> dict:
        """Two or three creators side by side (facts about checked claims, not a recommendation)."""
        r = api._http.get(f"{api.base}/creators/compare", params=[("handles", h) for h in handles])
        data = api._json(r)
        return {
            "creators": [
                {
                    "handle": c["handle"],
                    "checks": c["checks"],
                    "track_record": c["track_record"],
                    "stock_calls": c["ledger"]["counts"],
                    "official_flags": c["totals"].get("official_flags", 0),
                }
                for c in data["creators"]
            ],
            "missing": data["missing"],
            "note": data["note"],
        }

    @server.tool(annotations=read_only)
    def claim_ledger() -> dict:
        """Recent stock calls (price targets) and whether they came true."""
        data = api._get("/ledger")
        return {
            "counts": data["summary"]["counts"],
            "calls": [
                {
                    "ticker": e["entry"]["ticker"],
                    "said": e["entry"]["quote"],
                    "target": e["target"],
                    "deadline": e["entry"]["due_on"],
                    "status": e["entry"]["status"],
                    "creator": e["entry"]["creator"],
                }
                for e in data["summary"]["entries"][:25]
            ],
            "how_it_works": data["note"],
        }

    @server.tool(annotations=read_only)
    def sebi_rulebook() -> dict:
        """The red-flag checks PaperTrail runs and the official SEBI sources behind them."""
        data = api._get("/rulebook")
        return {
            "rules": [
                {"title": r["title"], "what": r["what"], "why": r["why"]} for r in data["rules"]
            ],
            "sources": [
                {"title": s["title"], "url": s["url"], "reference": s.get("reference_number")}
                for s in data["sources"]
            ],
        }

    return server


def main() -> None:  # pragma: no cover - starts a stdio server
    build_server().run("stdio")


if __name__ == "__main__":  # pragma: no cover
    main()

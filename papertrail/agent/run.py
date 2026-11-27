"""Run a complete check from the command line and print a readable report.

    uv run python -m papertrail.agent.run examples/hinglish_reel.txt
    uv run python -m papertrail.agent.run https://example.com/article --creator-name "Name"
    uv run python -m papertrail.agent.run examples/english_post.txt --json > check.json

Works offline by default (mock LLM + demo search). Set PAPERTRAIL_LLM_PROVIDER and
PAPERTRAIL_SEARCH_PROVIDER in .env to use real services.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from papertrail.agent.graph import AgentDeps, run_check
from papertrail.models import (
    STANDARD_NOTICES,
    VERDICT_DESCRIPTIONS,
    Check,
    CheckInput,
    CheckStatus,
    FlagBasis,
    InputKind,
)
from papertrail.report.render import render as render_file

ICONS = {
    "supported": "✅ Supported",
    "contradicted": "❌ Contradicted",
    "misleading": "⚠️  Misleading",
    "not_verifiable": "❔ Not verifiable",
}


def render_report(check: Check) -> str:
    out: list[str] = []
    add = out.append
    if check.status is CheckStatus.FAILED:
        return f"Check failed: {check.error}\n"
    add(f"PaperTrail check {check.id}  ·  language: {check.detected_language}")
    reg = check.registration
    add(f"SEBI registration: {reg.status.value.replace('_', ' ')}")
    add(f"  {reg.note}")
    add("")
    add(f"CLAIMS ({len(check.claims)})")
    for i, claim in enumerate(check.claims, 1):
        v = check.verdict_for(claim.id)
        add(f"\n{i}. {claim.text}")
        add(f'   Said: "{claim.quote}"')
        if v is None:
            continue
        add(
            f"   {ICONS[v.label.value]}  ·  "
            f"{v.confidence_band.value} confidence ({v.confidence:.2f})"
        )
        add(f"   {VERDICT_DESCRIPTIONS[v.label]}")
        add(f"   Why: {v.explanation.summary}")
        for step in v.explanation.reasoning:
            add(f"     - {step}")
        for gap in v.explanation.could_not_verify:
            add(f"   Could not verify: {gap}")
        for ev in check.evidence_for(claim.id):
            add(f"   [{ev.stance.value}] {ev.title} ({ev.url})")
            add(f'       "{ev.snippet[:160]}"')
    add("")
    add(f"SEBI RULEBOOK ({len(check.red_flags)} flag{'s' if len(check.red_flags) != 1 else ''})")
    for f in check.red_flags:
        tag = "OFFICIAL" if f.basis is FlagBasis.VERIFIED_RULE else "AI NOTE "
        add(f"\n[{tag}] {f.what_was_detected}")
        add(f'   Said: "{f.detected_text}"')
        add(f"   Why it matters: {f.why_it_matters}")
        add(f"   What you should know: {f.investor_takeaway}")
        if f.relevant_provision:
            add(f"   Provision: {f.relevant_provision}")
        for sid in f.rule_source_ids:
            src = next(s for s in check.regulatory_sources if s.id == sid)
            add(f"   Source: {src.title} ({src.reference_number or 'n/a'}) {src.url}")
    m = check.metrics
    add("")
    add(
        f"Run: {m.llm_calls} AI calls · {m.total_tokens} tokens · ${m.cost_usd:.4f} · "
        f"{m.duration_ms / 1000:.1f}s · {m.agent_steps} steps · {m.search_rounds} search round(s)"
    )
    for note in m.notes:
        add(f"Note: {note}")
    add("")
    add(*["\n".join(f"* {n}" for n in STANDARD_NOTICES)])
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a full PaperTrail check")
    parser.add_argument("source", help="Text/.srt/.vtt file, '-' for stdin, or an article URL")
    parser.add_argument("--creator-name")
    parser.add_argument("--creator-handle")
    parser.add_argument("--json", action="store_true", help="Print the Check as JSON")
    parser.add_argument("--no-ai-concerns", action="store_true")
    parser.add_argument(
        "--report", metavar="FILE", help="Also save a source-cited report (.html or .md)"
    )
    args = parser.parse_args(argv)

    src = args.source
    try:
        read_upload = None
        common = dict(creator_name=args.creator_name, creator_handle=args.creator_handle)
        if src.startswith(("http://", "https://")):
            check_input = CheckInput(kind=InputKind.ARTICLE_URL, url=src, **common)
        elif src == "-":
            check_input = CheckInput(kind=InputKind.TEXT, text=sys.stdin.read(), **common)
        elif Path(src).suffix.lower() in {".srt", ".vtt"}:
            check_input = CheckInput(kind=InputKind.VIDEO, upload_key=src, **common)
            read_upload = lambda key: Path(key).read_text(encoding="utf-8")  # noqa: E731
        else:
            check_input = CheckInput(
                kind=InputKind.TEXT, text=Path(src).read_text(encoding="utf-8"), **common
            )

    except ValidationError as exc:
        print(f"Check failed: the input is not valid ({exc.errors()[0]['msg']}).")
        return 1

    deps = AgentDeps.from_settings(
        read_upload=read_upload, include_ai_concerns=not args.no_ai_concerns
    )
    check = run_check(check_input, deps).check
    if args.json:
        print(check.model_dump_json(indent=2))
    else:
        print(render_report(check), end="")
    if args.report and check.status is CheckStatus.COMPLETED:
        fmt = "md" if args.report.lower().endswith(".md") else "html"
        Path(args.report).write_text(render_file(check, fmt), encoding="utf-8")
        print(f"Report saved to {args.report}", file=sys.stderr)
    return 0 if check.status is CheckStatus.COMPLETED else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

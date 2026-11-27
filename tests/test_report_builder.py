from datetime import date
from pathlib import Path

import pytest

from papertrail.agent.graph import AgentDeps, run_check
from papertrail.config import Settings
from papertrail.llm import MockProvider
from papertrail.models import Check, CheckInput, CheckStatus, InputKind
from papertrail.report.builder import ReportNotReadyError, build_report
from papertrail.tools.search import OfflineSearch

EXAMPLES = Path(__file__).parent.parent / "examples"


def completed_check(name="hinglish_reel.txt", handle="@demo_finfluencer") -> Check:
    deps = AgentDeps(
        provider=MockProvider(),
        search=OfflineSearch(),
        fetcher=None,
        registry=None,
        settings=Settings(_env_file=None),
        today=date(2026, 11, 26),
    )
    inp = CheckInput(kind=InputKind.TEXT, text=(EXAMPLES / name).read_text(), creator_handle=handle)
    return run_check(inp, deps).check


def test_report_orders_claims_and_numbers_citations():
    report = build_report(completed_check("english_post.txt"))
    assert [c.verdict for c in report.claims] == ["Contradicted", "Not verifiable", "Supported"]
    numbers = [cite.number for c in report.claims for cite in c.citations]
    assert numbers == list(range(1, len(numbers) + 1))  # 1..N, no gaps, in reading order
    assert report.counts == {
        "Contradicted": 1,
        "Misleading": 0,
        "Not verifiable": 1,
        "Supported": 1,
    }


def test_reasoning_uses_citation_numbers_not_internal_ids():
    report = build_report(completed_check())
    text = " ".join(r for c in report.claims for r in [*(c.reasoning), c.summary or ""])
    assert "evd_" not in text and "[1]" in text


def test_flags_cite_official_sources_with_refs():
    report = build_report(completed_check())
    assert report.flags and all(f.official for f in report.flags)
    refs = {s.ref for s in report.sources}
    assert all(r in refs for f in report.flags for r in f.source_refs)
    assert all(s.source.url.host.endswith("sebi.gov.in") for s in report.sources)


def test_report_carries_notices_registration_and_metrics():
    report = build_report(completed_check())
    assert any("not financial advice" in n for n in report.notices)
    assert report.registration_title == "Registration not checked"
    assert report.creator == "@demo_finfluencer" and report.language == "Hinglish"
    assert report.metrics["Prompt versions"].startswith("concerns concerns-v1")


def test_unfinished_checks_have_no_report():
    with pytest.raises(ReportNotReadyError):
        build_report(
            Check(
                input=CheckInput(kind=InputKind.TEXT, text="x y z"), status=CheckStatus.RESEARCHING
            )
        )


def test_parenthesised_ids_become_single_citation_brackets():
    report = build_report(completed_check())
    text = " ".join(r for c in report.claims for r in c.reasoning)
    assert "([" not in text and "guidance [1]" in text

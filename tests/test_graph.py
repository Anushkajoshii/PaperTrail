from datetime import date
from pathlib import Path

import pytest

from papertrail.agent.graph import AgentDeps, build_graph, run_check
from papertrail.config import Settings
from papertrail.llm import MockProvider
from papertrail.models import (
    Check,
    CheckInput,
    CheckStatus,
    ClaimType,
    FlagBasis,
    InputKind,
    RedFlagKind,
    RegistrationStatus,
    VerdictLabel,
)
from papertrail.tools.fetch import FetchedPage
from papertrail.tools.search import OfflineSearch

EXAMPLES = Path(__file__).parent.parent / "examples"
TODAY = date(2026, 11, 26)


def deps(**kw):
    base = dict(
        provider=MockProvider(),
        search=OfflineSearch(),
        fetcher=None,
        registry=None,
        settings=Settings(_env_file=None),
        today=TODAY,
    )
    return AgentDeps(**(base | kw))


def text_input(name):
    return CheckInput(kind=InputKind.TEXT, text=(EXAMPLES / name).read_text())


def verdicts_by_type(check: Check):
    return {c.claim_type: check.verdict_for(c.id).label for c in check.claims}


def test_full_offline_run_on_english_post():
    events, details = [], []

    def on_progress(status, detail):
        if not events or events[-1] is not status:  # one entry per stage
            events.append(status)
        details.append(detail)

    run = run_check(text_input("english_post.txt"), deps(on_progress=on_progress))
    check = run.check
    assert check.status is CheckStatus.COMPLETED
    assert verdicts_by_type(check) == {
        ClaimType.MARKET_FACT: VerdictLabel.SUPPORTED,  # Nifty 26,277 matches demo data
        ClaimType.COMPANY_FACT: VerdictLabel.CONTRADICTED,  # ₹19,000 cr vs ₹16,500 cr
        ClaimType.PAST_PERFORMANCE: VerdictLabel.NOT_VERIFIABLE,  # private portfolio
    }
    assert [e for e in events if e is not CheckStatus.RESEARCHING] == [
        CheckStatus.TRANSCRIBING,
        CheckStatus.EXTRACTING,
        CheckStatus.JUDGING,
        CheckStatus.CHECKING_RULEBOOK,
        CheckStatus.COMPLETED,
    ]
    assert "Weighing the evidence: claim 1 of 3" in details  # progress for every claim
    m = check.metrics
    assert m.agent_steps >= 6 and m.llm_calls >= 3 and m.prompt_versions["judge"] == "judge-v1"
    # Round-trips through JSON (what the API will return and DynamoDB will store).
    assert Check.model_validate_json(check.model_dump_json()) == check


def test_full_offline_run_on_hinglish_reel():
    check = run_check(text_input("hinglish_reel.txt"), deps()).check
    labels = verdicts_by_type(check)
    assert labels[ClaimType.CREDENTIAL] is VerdictLabel.NOT_VERIFIABLE  # register not loaded
    assert labels[ClaimType.STOCK_CALL] is VerdictLabel.NOT_VERIFIABLE  # future target
    assert labels[ClaimType.RETURN_PROMISE] is VerdictLabel.MISLEADING
    assert check.registration.status is RegistrationStatus.NOT_CHECKED
    kinds = {f.kind for f in check.red_flags if f.basis is FlagBasis.VERIFIED_RULE}
    assert {RedFlagKind.GUARANTEED_RETURNS, RedFlagKind.TIP_GROUP_SOLICITATION} <= kinds
    for v in check.verdicts:
        assert v.explanation.summary and v.explanation.confidence_note


def test_evidence_loop_runs_a_second_round_when_evidence_is_thin():
    run = run_check(
        CheckInput(kind=InputKind.TEXT, text="Sunrise Widgets gave 900% in 2021."), deps()
    )
    assert run.check.status is CheckStatus.COMPLETED
    assert run.check.metrics.search_rounds == 2  # nothing relevant in round 1, so one more try
    assert run.check.verdicts[0].label is VerdictLabel.NOT_VERIFIABLE


def test_step_limit_stops_runaway_runs_cleanly():
    tiny = Settings(_env_file=None, max_agent_steps=3)
    run = run_check(text_input("english_post.txt"), deps(settings=tiny))
    assert run.check.status is CheckStatus.FAILED
    assert "safety limit" in run.check.error
    assert run.check.verdicts == []  # no partial results


def test_article_url_input_uses_fetcher_and_reports_removed_instructions():
    class Fetcher:
        def fetch(self, url):
            return FetchedPage(
                url=url,
                final_url=url,
                title="t",
                site_name=None,
                published=None,
                text="Nifty 50 hit an all-time high of 26,277 on 27 September 2024.",
                removed_instruction_count=2,
            )

    check = run_check(
        CheckInput(kind=InputKind.ARTICLE_URL, url="https://news.example.com/a"),
        deps(fetcher=Fetcher()),
    ).check
    assert (
        check.status is CheckStatus.COMPLETED and check.verdicts[0].label is VerdictLabel.SUPPORTED
    )
    assert any("instruction-like" in n for n in check.metrics.notes)


def test_subtitle_upload_and_missing_transcriber():
    srt = (
        "1\n00:00:01,000 --> 00:00:05,000\n"
        "Nifty 50 hit an all-time high of 26,277 on 27 September 2024.\n"
    )
    ok = run_check(
        CheckInput(kind=InputKind.VIDEO, upload_key="u/clip.srt"), deps(read_upload=lambda key: srt)
    ).check
    assert ok.status is CheckStatus.COMPLETED and ok.claims[0].timestamp_seconds == 1.0
    no_aws = run_check(CheckInput(kind=InputKind.VIDEO, upload_key="u/clip.mp4"), deps()).check
    assert no_aws.status is CheckStatus.FAILED and ".srt/.vtt/.txt" in no_aws.error


def test_unexpected_errors_become_failed_checks_without_leaking_internals():
    class Exploding:
        name = "boom"

        def complete(self, request, *, feedback=None):
            raise KeyError("internal detail")

    check = run_check(text_input("english_post.txt"), deps(provider=Exploding())).check
    assert check.status is CheckStatus.FAILED
    assert "internal detail" not in check.error and "KeyError" in check.error


def test_graph_structure():
    g = build_graph(deps()).get_graph()
    assert {"ingest", "extract", "registration", "research", "judge", "rulebook"} <= set(g.nodes)


@pytest.mark.parametrize("include", [True, False])
def test_ai_concerns_switch(include):
    check = run_check(
        CheckInput(kind=InputKind.TEXT, text="My fund gives 8% every month."),
        deps(include_ai_concerns=include),
    ).check
    has_ai = any(f.basis is FlagBasis.POTENTIAL_CONCERN for f in check.red_flags)
    assert has_ai is include

"""The PaperTrail agent: a LangGraph state machine from raw content to a finished Check.

    ingest -> extract -> registration -> research --(evidence loop)--> judge -> rulebook -> finalize
                                            ^____________|

* **ingest**: pasted text as is, article URL through the safe fetcher, subtitles/transcripts from
  an upload, or audio/video through Amazon Transcribe.
* **research** loops: claims without clearly relevant evidence get one more, broader search
  round, up to ``max_search_rounds``.
* **Max-steps guard**: every node counts a step. Going over ``max_agent_steps`` stops the run
  with a clear error, and LangGraph's own recursion limit backs this up. A bug can never loop
  forever or run up costs.
* **All-or-nothing**: if anything fatal happens the Check is marked failed and no partial
  verdicts are shown (users must never see half a fact-check).

Dependencies are injected (``AgentDeps``), so tests run the real graph fully offline.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import PurePath
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from papertrail.agent.extract import extract_claims
from papertrail.agent.judge import JUDGE_PROMPT_VERSION, judge_claim
from papertrail.agent.prompts import EXTRACT_PROMPT_VERSION
from papertrail.agent.research import ResearchDeps, ResearchResult, research_claim
from papertrail.config import Settings, get_settings
from papertrail.llm import Provider, UsageLog, get_provider
from papertrail.models import (
    Check,
    CheckInput,
    CheckMetrics,
    CheckStatus,
    Claim,
    ClaimType,
    Evidence,
    InputKind,
    Language,
    RedFlag,
    RegulatorySource,
    SebiRegistration,
    TranscriptSegment,
    Verdict,
)
from papertrail.rulebook.concerns import CONCERNS_PROMPT_VERSION, check_rulebook
from papertrail.rulebook.registry import Registry, lookup_registration
from papertrail.tools.fetch import PageFetcher
from papertrail.tools.search import SearchProvider, get_search_provider
from papertrail.tools.transcribe import (
    SUPPORTED_TEXT,
    AwsTranscriber,
    TranscriptionError,
    transcript_from_text_file,
)

log = logging.getLogger(__name__)

ProgressFn = Callable[[CheckStatus, str], None]


class AgentStepLimitError(RuntimeError):
    pass


class IngestError(RuntimeError):
    pass


@dataclass
class AgentDeps:
    provider: Provider
    search: SearchProvider
    fetcher: PageFetcher | None = None
    registry: Registry | None = None
    transcriber: AwsTranscriber | None = None
    read_upload: Callable[[str], str] | None = None  # upload key -> text (subtitles/transcripts)
    settings: Settings = field(default_factory=get_settings)
    today: date = field(default_factory=date.today)
    on_progress: ProgressFn | None = None
    include_ai_concerns: bool = True

    @classmethod
    def from_settings(cls, settings: Settings | None = None, **overrides: Any) -> AgentDeps:
        s = settings or get_settings()
        base: dict[str, Any] = dict(
            provider=get_provider(s),
            search=get_search_provider(s),
            fetcher=PageFetcher.from_settings(s),
            registry=Registry.load(s.registry_snapshot_path),
            settings=s,
        )
        return cls(**(base | overrides))


class AgentState(TypedDict, total=False):
    input: CheckInput
    transcript: str
    segments: list[TranscriptSegment]
    language: Language
    claims: list[Claim]
    registration: SebiRegistration
    research: dict[str, ResearchResult]
    research_round: int
    verdicts: list[Verdict]
    evidence: list[Evidence]
    flags: list[RedFlag]
    sources: list[RegulatorySource]
    steps: int
    usage: UsageLog
    notes: list[str]


def build_graph(deps: AgentDeps):
    s = deps.settings

    def progress(status: CheckStatus, detail: str = "") -> None:
        if deps.on_progress:
            deps.on_progress(status, detail)

    def step(name: str, fn: Callable[[AgentState], dict]) -> Callable[[AgentState], dict]:
        def wrapped(state: AgentState) -> dict:
            steps = state.get("steps", 0) + 1
            if steps > s.max_agent_steps:
                raise AgentStepLimitError(
                    f"Stopped after {s.max_agent_steps} steps (safety limit) at '{name}'"
                )
            update = fn(state)
            update["steps"] = steps
            return update

        return wrapped

    # -- nodes -------------------------------------------------------------------------------

    def ingest(state: AgentState) -> dict:
        inp = state["input"]
        progress(CheckStatus.TRANSCRIBING, "Reading the content")
        notes = list(state.get("notes", []))
        segments: list[TranscriptSegment] = []
        if inp.kind is InputKind.TEXT:
            text = inp.text or ""
        elif inp.kind is InputKind.ARTICLE_URL:
            if deps.fetcher is None:
                raise IngestError("Article links need the page fetcher, which is not configured")
            page = deps.fetcher.fetch(str(inp.url))
            text = page.text
            if page.removed_instruction_count:
                notes.append(
                    f"{page.removed_instruction_count} instruction-like sentence(s) were removed "
                    "from the article before analysis."
                )
        else:
            key = inp.upload_key or ""
            ext = PurePath(key).suffix.lower().lstrip(".")
            if ext in SUPPORTED_TEXT and deps.read_upload is not None:
                t = transcript_from_text_file(key, deps.read_upload(key))
            elif deps.transcriber is not None:
                t = deps.transcriber.transcribe(key)
            else:
                raise IngestError(
                    "Audio/video transcription needs AWS (set up in Part 10). Upload a "
                    ".srt/.vtt/.txt transcript or paste the text instead."
                )
            text, segments = t.text, t.segments
        if not text.strip():
            raise IngestError("The content is empty, so there is nothing to check")
        return {"transcript": text, "segments": segments, "notes": notes}

    def extract(state: AgentState) -> dict:
        progress(CheckStatus.EXTRACTING, "Finding statements that can be fact-checked")
        inp = state["input"]
        result = extract_claims(
            state["transcript"],
            provider=deps.provider,
            segments=state.get("segments") or None,
            language_hint=inp.language_hint,
        )
        usage = state.get("usage") or UsageLog()
        usage.calls.extend(result.usage.calls)
        notes = list(state.get("notes", []))
        if result.dropped:
            ungrounded = sum(d.reason == "quote not found in transcript" for d in result.dropped)
            if ungrounded:
                notes.append(
                    f"{ungrounded} AI-suggested claim(s) were dropped because their "
                    "quote was not found in the content."
                )
        return {
            "claims": result.claims,
            "language": result.language,
            "usage": usage,
            "notes": notes,
        }

    def registration(state: AgentState) -> dict:
        inp = state["input"]
        reg = lookup_registration(
            deps.registry,
            name=inp.creator_name or inp.creator_handle,
            text=state["transcript"],
            today=deps.today,
        )
        return {"registration": reg}

    def research(state: AgentState) -> dict:
        round_no = state.get("research_round", 0) + 1
        progress(CheckStatus.RESEARCHING, f"Looking for evidence (round {round_no})")
        rdeps = ResearchDeps(
            search=deps.search,
            fetcher=deps.fetcher,
            max_results=s.search_max_results,
            pages_to_fetch=s.pages_to_fetch_per_claim,
            today=deps.today,
        )
        found = dict(state.get("research", {}))
        for claim in state["claims"]:
            if claim.claim_type is ClaimType.CREDENTIAL:
                continue  # decided from the SEBI register, not web search
            previous = found.get(claim.id)
            if previous is not None and previous.has_enough:
                continue
            found[claim.id] = research_claim(
                claim,
                rdeps,
                round_no=round_no,
                creator_name=state["input"].creator_name,
                previous=previous,
            )
        return {"research": found, "research_round": round_no}

    def needs_more_research(state: AgentState) -> str:
        if state.get("research_round", 0) >= s.max_search_rounds:
            return "judge"
        lacking = [r for r in state.get("research", {}).values() if not r.has_enough]
        return "research" if lacking else "judge"

    def judge(state: AgentState) -> dict:
        progress(CheckStatus.JUDGING, "Weighing the evidence for each claim")
        usage = state.get("usage") or UsageLog()
        verdicts, evidence = [], []
        notes = list(state.get("notes", []))
        for claim in state["claims"]:
            res = state.get("research", {}).get(claim.id)
            result = judge_claim(
                claim,
                res.candidates if res else [],
                provider=deps.provider,
                registration=state["registration"],
                today=deps.today,
                usage_log=usage,
            )
            verdicts.append(result.verdict)
            evidence.extend(result.evidence)
            if result.error:
                notes.append(
                    "The AI judge could not assess one claim; it is shown as not verifiable."
                )
        return {"verdicts": verdicts, "evidence": evidence, "usage": usage, "notes": notes}

    def rulebook(state: AgentState) -> dict:
        progress(CheckStatus.CHECKING_RULEBOOK, "Comparing with official SEBI rules and guidance")
        inp = state["input"]
        rb = check_rulebook(
            state["transcript"],
            state["claims"],
            state["registration"],
            creator_name=inp.creator_name,
            provider=deps.provider,
            include_ai_concerns=deps.include_ai_concerns,
        )
        usage = state.get("usage") or UsageLog()
        usage.calls.extend(rb.concerns.usage.calls)
        return {"flags": rb.flags, "sources": rb.sources, "usage": usage}

    graph = StateGraph(AgentState)
    for name, fn in [
        ("ingest", ingest),
        ("extract", extract),
        ("registration", registration),
        ("research", research),
        ("judge", judge),
        ("rulebook", rulebook),
    ]:
        graph.add_node(name, step(name, fn))
    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "extract")
    graph.add_edge("extract", "registration")
    graph.add_edge("registration", "research")
    graph.add_conditional_edges(
        "research", needs_more_research, {"research": "research", "judge": "judge"}
    )
    graph.add_edge("judge", "rulebook")
    graph.add_edge("rulebook", END)
    return graph.compile()


@dataclass
class AgentRun:
    check: Check
    state: dict = field(default_factory=dict)


def run_check(check_input: CheckInput, deps: AgentDeps, *, check_id: str | None = None) -> AgentRun:
    """Run the whole pipeline and return a validated Check (completed or failed)."""
    started = time.perf_counter()
    graph = build_graph(deps)
    ids = {"id": check_id} if check_id else {}
    try:
        state = graph.invoke(
            {"input": check_input, "steps": 0, "notes": [], "usage": UsageLog()},
            config={"recursion_limit": deps.settings.max_agent_steps + 5},
        )
    except Exception as exc:
        log.exception("Check failed")
        message = (
            str(exc)
            if isinstance(exc, IngestError | TranscriptionError | AgentStepLimitError)
            else (f"The check could not be completed ({type(exc).__name__}).")
        )
        if deps.on_progress:
            deps.on_progress(CheckStatus.FAILED, message)
        failed = Check(input=check_input, status=CheckStatus.FAILED, error=message, **ids)
        return AgentRun(failed)

    usage: UsageLog = state["usage"]
    research = state.get("research", {})
    metrics = CheckMetrics(
        llm_calls=len(usage.calls),
        total_tokens=usage.total_tokens,
        cost_usd=usage.total_cost_usd,
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
        agent_steps=state["steps"],
        search_rounds=state.get("research_round", 0),
        pages_fetched=sum(r.pages_fetched for r in research.values()),
        prompt_versions={
            "extract": EXTRACT_PROMPT_VERSION,
            "judge": JUDGE_PROMPT_VERSION,
            "concerns": CONCERNS_PROMPT_VERSION,
        },
        notes=[*state.get("notes", []), *[e for r in research.values() for e in r.errors][:10]],
    )
    check = Check(
        input=check_input,
        status=CheckStatus.COMPLETED,
        detected_language=state.get("language"),
        transcript=state["transcript"],
        claims=state["claims"],
        evidence=state.get("evidence", []),
        verdicts=state.get("verdicts", []),
        red_flags=state.get("flags", []),
        regulatory_sources=state.get("sources", []),
        registration=state["registration"],
        metrics=metrics,
        **ids,
    )
    if deps.on_progress:
        deps.on_progress(CheckStatus.COMPLETED, "Done")
    return AgentRun(check, state)

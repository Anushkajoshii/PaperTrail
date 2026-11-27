"""Turn a finished Check into a report structure with numbered citations.

The same structure feeds every output format (HTML for print/PDF, Markdown), so the content
and the citation numbers are identical across formats.

* Web evidence is numbered [1], [2], ... in the order claims appear.
* Official SEBI documents are listed separately as [S1], [S2], ...
* Internal evidence ids in the AI's reasoning are replaced with the citation number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from papertrail import __version__
from papertrail.models import (
    CLAIM_TYPE_LABELS,
    STANDARD_NOTICES,
    VERDICT_DESCRIPTIONS,
    Check,
    CheckStatus,
    Evidence,
    FlagBasis,
    Language,
    RegistrationStatus,
    RegulatorySource,
    Stance,
    VerdictLabel,
)

REPORT_VERSION = "report-v1"

VERDICT_TITLES = {
    VerdictLabel.SUPPORTED: "Supported",
    VerdictLabel.CONTRADICTED: "Contradicted",
    VerdictLabel.MISLEADING: "Misleading",
    VerdictLabel.NOT_VERIFIABLE: "Not verifiable",
}
# Most serious first, so readers see what matters most at the top.
VERDICT_ORDER = [
    VerdictLabel.CONTRADICTED,
    VerdictLabel.MISLEADING,
    VerdictLabel.NOT_VERIFIABLE,
    VerdictLabel.SUPPORTED,
]
STANCE_TITLES = {
    Stance.SUPPORTS: "Supports the claim",
    Stance.CONTRADICTS: "Contradicts the claim",
    Stance.CONTEXT: "Useful context",
}
SOURCE_TYPE_TITLES = {
    "regulator": "Regulator",
    "exchange": "Stock exchange",
    "company_filing": "Company filing",
    "data_provider": "Data provider",
    "reputable_news": "News outlet",
    "blog": "Blog",
    "social": "Social media",
    "other": "Other website",
}
VERIFICATION_TITLES = {
    "full_text": "Read in full",
    "official_listing": "Title and date confirmed on SEBI's site",
    "quoted_in_sebi_orders": "Wording as quoted in SEBI's own orders",
}
REGISTRATION_TITLES = {
    RegistrationStatus.REGISTERED_IA: "Registered with SEBI as an Investment Adviser",
    RegistrationStatus.REGISTERED_RA: "Registered with SEBI as a Research Analyst",
    RegistrationStatus.REGISTERED_IA_AND_RA: (
        "Registered with SEBI as an Investment Adviser and Research Analyst"
    ),
    RegistrationStatus.NOT_FOUND: "Not found in our copy of SEBI's register",
    RegistrationStatus.NOT_CHECKED: "Registration not checked",
}
LANGUAGE_TITLES = {
    Language.ENGLISH: "English",
    Language.HINDI: "Hindi",
    Language.HINGLISH: "Hinglish",
}
LIMITATIONS = (
    "PaperTrail cannot judge intent or honesty; it checks statements against evidence.",
    "It cannot prove a legal violation; only SEBI or a court can decide that.",
    "It only knows what it can find: private groups, paid courses and deleted posts are "
    "usually out of reach.",
    "AI can make mistakes; every verdict lists its sources so you can check them yourself.",
)


def _band(score: float) -> str:
    return "High" if score >= 0.75 else "Medium" if score >= 0.45 else "Low"


@dataclass
class Citation:
    number: int
    evidence: Evidence
    stance_title: str
    source_type_title: str
    quality: dict[str, str]


@dataclass
class ReportClaim:
    number: int
    text: str
    quote: str
    claim_type: str
    timestamp: str | None
    tickers: list[str]
    verdict: str | None
    verdict_key: str | None
    verdict_description: str | None
    confidence: float | None
    confidence_band: str | None
    summary: str | None
    reasoning: list[str]
    could_not_verify: list[str]
    confidence_note: str | None
    citations: list[Citation]


@dataclass
class ReportFlag:
    official: bool
    label: str
    what: str
    said: str
    why: str
    takeaway: str
    provision: str | None
    source_refs: list[str]  # e.g. ["S1", "S2"]


@dataclass
class ReportSource:
    ref: str
    source: RegulatorySource
    verification: str


@dataclass
class Report:
    check_id: str
    generated_at: datetime
    checked_at: datetime
    creator: str | None
    language: str | None
    input_summary: str
    counts: dict[str, int]
    registration_title: str
    registration_detail: list[str]
    claims: list[ReportClaim]
    flags: list[ReportFlag]
    sources: list[ReportSource]
    notices: tuple[str, ...]
    limitations: tuple[str, ...]
    metrics: dict[str, str]
    version: str = REPORT_VERSION
    app_version: str = __version__
    all_citations: list[Citation] = field(default_factory=list)


class ReportNotReadyError(ValueError):
    pass


def _timestamp(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def _input_summary(check: Check) -> str:
    inp = check.input
    if inp.kind.value == "article_url":
        return f"Article: {inp.url}"
    if inp.kind.value == "text":
        return f"Pasted text ({len(inp.text or ''):,} characters)"
    return f"Uploaded {inp.kind.value} file"


def build_report(check: Check, *, generated_at: datetime | None = None) -> Report:
    if check.status is not CheckStatus.COMPLETED:
        raise ReportNotReadyError("A report is only available for completed checks")

    verdicts = {v.claim_id: v for v in check.verdicts}
    order = {label: i for i, label in enumerate(VERDICT_ORDER)}
    claims_sorted = sorted(
        check.claims,
        key=lambda c: order.get(verdicts[c.id].label if c.id in verdicts else None, len(order)),
    )

    numbers: dict[str, int] = {}
    citations: list[Citation] = []
    report_claims: list[ReportClaim] = []
    for i, claim in enumerate(claims_sorted, 1):
        claim_citations = []
        for ev in sorted(check.evidence_for(claim.id), key=lambda e: list(Stance).index(e.stance)):
            numbers[ev.id] = len(numbers) + 1
            cite = Citation(
                number=numbers[ev.id],
                evidence=ev,
                stance_title=STANCE_TITLES[ev.stance],
                source_type_title=SOURCE_TYPE_TITLES.get(
                    ev.source_type.value, ev.source_type.value
                ),
                quality={
                    "Reliability": _band(ev.quality.reliability),
                    "Recency": _band(ev.quality.recency),
                    "Relevance": _band(ev.quality.relevance),
                },
            )
            claim_citations.append(cite)
            citations.append(cite)

        def readable(text: str) -> str:
            # "(evd_x)" and "evd_x" both become "[n]".
            def sub(m: re.Match[str]) -> str:
                eid = m.group(1)
                return f"[{numbers[eid]}]" if eid in numbers else m.group(0)

            return re.sub(r"\(?\b(evd_[A-Za-z0-9_]+)\b\)?", sub, text)

        v = verdicts.get(claim.id)
        report_claims.append(
            ReportClaim(
                number=i,
                text=claim.text,
                quote=claim.quote,
                claim_type=CLAIM_TYPE_LABELS.get(claim.claim_type, claim.claim_type.value),
                timestamp=_timestamp(claim.timestamp_seconds),
                tickers=list(claim.tickers),
                verdict=VERDICT_TITLES[v.label] if v else None,
                verdict_key=v.label.value if v else None,
                verdict_description=VERDICT_DESCRIPTIONS[v.label] if v else None,
                confidence=v.confidence if v else None,
                confidence_band=v.confidence_band.value.capitalize() if v else None,
                summary=readable(v.explanation.summary) if v else None,
                reasoning=[readable(r) for r in v.explanation.reasoning] if v else [],
                could_not_verify=list(v.explanation.could_not_verify) if v else [],
                confidence_note=v.explanation.confidence_note if v else None,
                citations=claim_citations,
            )
        )

    source_refs = {s.id: f"S{i}" for i, s in enumerate(check.regulatory_sources, 1)}
    flags = [
        ReportFlag(
            official=f.basis is FlagBasis.VERIFIED_RULE,
            label=f.label,
            what=f.what_was_detected,
            said=f.detected_text,
            why=f.why_it_matters,
            takeaway=f.investor_takeaway,
            provision=f.relevant_provision,
            source_refs=[source_refs[sid] for sid in f.rule_source_ids if sid in source_refs],
        )
        for f in sorted(check.red_flags, key=lambda f: f.basis is FlagBasis.POTENTIAL_CONCERN)
    ]

    reg = check.registration
    reg_detail = []
    if reg.matched_name:
        reg_detail.append(f"{reg.matched_name} ({', '.join(reg.registration_numbers)})")
    if reg.match_basis:
        reg_detail.append(f"Matched by {reg.match_basis.replace('_', ' ')}.")
    if reg.registry_snapshot_date:
        reg_detail.append(f"Register copy dated {reg.registry_snapshot_date:%d %b %Y}.")
    reg_detail.append(reg.note)

    counts = {VERDICT_TITLES[label]: 0 for label in VERDICT_ORDER}
    for v in check.verdicts:
        counts[VERDICT_TITLES[v.label]] += 1

    m = check.metrics
    return Report(
        check_id=check.id,
        generated_at=generated_at or datetime.now(UTC),
        checked_at=check.updated_at,
        creator=check.input.creator_handle,
        language=LANGUAGE_TITLES.get(check.detected_language) if check.detected_language else None,
        input_summary=_input_summary(check),
        counts=counts,
        registration_title=REGISTRATION_TITLES[reg.status],
        registration_detail=reg_detail,
        claims=report_claims,
        flags=flags,
        sources=[
            ReportSource(
                ref=source_refs[s.id],
                source=s,
                verification=VERIFICATION_TITLES.get(s.verification_level.value, ""),
            )
            for s in check.regulatory_sources
        ],
        notices=STANDARD_NOTICES,
        limitations=LIMITATIONS,
        metrics={
            "AI calls": str(m.llm_calls),
            "Estimated AI cost": f"${m.cost_usd:.4f}",
            "Search rounds": str(m.search_rounds),
            "Prompt versions": ", ".join(f"{k} {v}" for k, v in sorted(m.prompt_versions.items())),
        },
        all_citations=citations,
    )

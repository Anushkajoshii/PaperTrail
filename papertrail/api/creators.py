"""Creator profiles and side-by-side comparison, built from stored checks and the Claim Ledger.

Design rule (ADR-018): a profile shows *counts with their sample size*, never a single score.
PaperTrail judges claims, not people, and small samples are labelled as such.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from pydantic import Field

from papertrail.api.schemas import CheckSummary, _Out
from papertrail.ledger.models import LEDGER_STATUS_DESCRIPTIONS, LedgerEntry, LedgerStatus
from papertrail.models import Check, CheckStatus, FlagBasis, RegistrationStatus, VerdictLabel
from papertrail.store.checks import normalize_handle

MIN_SAMPLE = 5  # below this many assessed claims, shares are not shown

PROFILE_NOTE = (
    "These are facts about checked claims, not a judgement of the person. Counts depend on which "
    "content was checked, so a few checks can't describe a whole channel."
)
COMPARE_NOTE = (
    "Side-by-side facts about checked claims. This is not a recommendation to follow, avoid, "
    "buy or sell anything, and creators with more checks are not directly comparable to those "
    "with fewer."
)
LEDGER_NOTE = (
    "Stock calls are tracked from the day PaperTrail first saw them. A call counts as hit if the "
    "price reached the target by the deadline; when no deadline was stated, 90 days are used."
)


class TrackRecord(_Out):
    claims_checked: int
    assessed: int = Field(description="Claims that got a verdict other than 'not verifiable'.")
    supported: int
    contradicted: int
    misleading: int
    not_verifiable: int
    supported_share: float | None = Field(
        description=f"Supported / assessed. Empty below {MIN_SAMPLE} assessed claims."
    )
    enough_data: bool


class LedgerEntryView(_Out):
    entry: LedgerEntry
    target: float | None
    status_description: str

    @classmethod
    def of(cls, e: LedgerEntry) -> LedgerEntryView:
        return cls(
            entry=e,
            target=e.resolved_target(),
            status_description=LEDGER_STATUS_DESCRIPTIONS[e.status],
        )


class LedgerSummary(_Out):
    counts: dict[str, int]
    settled: int = Field(description="Hit + missed: calls that could be checked against prices.")
    hit_share: float | None = Field(description="Hit / settled, when at least 5 are settled.")
    entries: list[LedgerEntryView]


class TimelineItem(_Out):
    date: date
    check_id: str
    official: bool = Field(
        description="True: a verified SEBI rule. False: an AI potential concern."
    )
    kind: str
    what: str
    quote: str


class CreatorProfile(_Out):
    handle: str
    checks: int
    first_checked: date
    last_checked: date
    registration: str = Field(description="SEBI registration status from the latest check.")
    totals: dict[str, int]
    track_record: TrackRecord
    ledger: LedgerSummary
    timeline: list[TimelineItem]
    recent: list[CheckSummary]
    note: str = PROFILE_NOTE


class CompareView(_Out):
    creators: list[CreatorProfile]
    missing: list[str] = Field(description="Handles with no checks yet.")
    note: str = COMPARE_NOTE


class LedgerView(_Out):
    summary: LedgerSummary
    note: str = LEDGER_NOTE


def _share(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole >= MIN_SAMPLE else None


def track_record(checks: list[Check]) -> TrackRecord:
    labels = Counter(v.label for c in checks for v in c.verdicts)
    assessed = sum(n for label, n in labels.items() if label is not VerdictLabel.NOT_VERIFIABLE)
    supported = labels[VerdictLabel.SUPPORTED]
    return TrackRecord(
        claims_checked=sum(len(c.claims) for c in checks),
        assessed=assessed,
        supported=supported,
        contradicted=labels[VerdictLabel.CONTRADICTED],
        misleading=labels[VerdictLabel.MISLEADING],
        not_verifiable=labels[VerdictLabel.NOT_VERIFIABLE],
        supported_share=_share(supported, assessed),
        enough_data=assessed >= MIN_SAMPLE,
    )


def ledger_summary(entries: list[LedgerEntry]) -> LedgerSummary:
    counts = Counter(e.status.value for e in entries)
    hit, missed = counts[LedgerStatus.HIT.value], counts[LedgerStatus.MISSED.value]
    return LedgerSummary(
        counts={s.value: counts[s.value] for s in LedgerStatus},
        settled=hit + missed,
        hit_share=_share(hit, hit + missed),
        entries=[LedgerEntryView.of(e) for e in entries],
    )


def timeline(checks: list[Check]) -> list[TimelineItem]:
    items = [
        TimelineItem(
            date=c.created_at.date(),
            check_id=c.id,
            official=f.basis is FlagBasis.VERIFIED_RULE,
            kind=f.kind.value,
            what=f.what_was_detected,
            quote=f.detected_text,
        )
        for c in checks
        for f in c.red_flags
    ]
    return sorted(items, key=lambda i: (i.date, i.official), reverse=True)


REGISTRATION_TEXT = {
    RegistrationStatus.REGISTERED_IA: "Registered as an Investment Adviser",
    RegistrationStatus.REGISTERED_RA: "Registered as a Research Analyst",
    RegistrationStatus.REGISTERED_IA_AND_RA: (
        "Registered as an Investment Adviser and Research Analyst"
    ),
    RegistrationStatus.NOT_FOUND: "Not found in our copy of SEBI's register",
    RegistrationStatus.NOT_CHECKED: "Not checked",
}


def build_profile(
    handle: str, checks: list[Check], entries: list[LedgerEntry]
) -> CreatorProfile | None:
    done = sorted(
        (c for c in checks if c.status is CheckStatus.COMPLETED),
        key=lambda c: c.created_at,
        reverse=True,
    )
    if not done:
        return None
    totals: Counter[str] = Counter()
    summaries = [CheckSummary.of(c) for c in done]
    for s in summaries:
        totals.update(s.verdicts)
        totals["official_flags"] += s.official_flags
        totals["potential_concerns"] += s.potential_concerns
    return CreatorProfile(
        handle=f"@{normalize_handle(handle)}",
        checks=len(done),
        first_checked=done[-1].created_at.date(),
        last_checked=done[0].created_at.date(),
        registration=REGISTRATION_TEXT[done[0].registration.status],
        totals=dict(totals),
        track_record=track_record(done),
        ledger=ledger_summary(entries),
        timeline=timeline(done)[:50],
        recent=summaries[:20],
    )

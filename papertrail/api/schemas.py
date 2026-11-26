"""Request and response models for the HTTP API (they also drive the OpenAPI docs)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from papertrail.models import (
    STATUS_DESCRIPTIONS,
    VERDICT_DESCRIPTIONS,
    Check,
    CheckStatus,
    FlagBasis,
    Language,
    RegulatorySource,
    VerdictLabel,
)

# Rough progress for the progress screen (the stages always run in this order).
PROGRESS = {
    CheckStatus.QUEUED: 5,
    CheckStatus.TRANSCRIBING: 15,
    CheckStatus.EXTRACTING: 30,
    CheckStatus.RESEARCHING: 55,
    CheckStatus.JUDGING: 75,
    CheckStatus.CHECKING_RULEBOOK: 90,
    CheckStatus.COMPLETED: 100,
    CheckStatus.FAILED: 100,
}


class CreateCheckRequest(BaseModel):
    """Submit pasted text or an article link. Use POST /checks/upload for files."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "kind": "text",
                    "text": "Guaranteed 5% every month in my Telegram group!",
                    "creator_handle": "@democreator",
                }
            ]
        },
    )

    kind: Literal["text", "article_url"]
    text: str | None = None
    url: HttpUrl | None = None
    creator_handle: str | None = Field(default=None, max_length=100)
    creator_name: str | None = Field(default=None, max_length=200)
    language_hint: Language | None = None


class _Out(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class ErrorBody(_Out):
    code: str
    message: str


class ErrorResponse(_Out):
    error: ErrorBody


class CheckAccepted(_Out):
    id: str
    status: CheckStatus
    status_description: str
    status_url: str
    poll_after_seconds: int = 2


class CheckView(_Out):
    """A check plus plain-language helpers the UI shows next to it."""

    check: Check
    status_description: str
    progress_percent: int
    is_finished: bool
    notices: list[str]
    verdict_descriptions: dict[VerdictLabel, str]

    @classmethod
    def of(cls, check: Check) -> CheckView:
        return cls(
            check=check,
            status_description=STATUS_DESCRIPTIONS[check.status],
            progress_percent=PROGRESS[check.status],
            is_finished=check.status in (CheckStatus.COMPLETED, CheckStatus.FAILED),
            notices=list(check.notices),
            verdict_descriptions=VERDICT_DESCRIPTIONS,
        )


class CheckSummary(_Out):
    id: str
    created_at: datetime
    status: CheckStatus
    claims: int
    verdicts: dict[str, int]
    official_flags: int
    potential_concerns: int

    @classmethod
    def of(cls, check: Check) -> CheckSummary:
        counts: dict[str, int] = {}
        for v in check.verdicts:
            counts[v.label.value] = counts.get(v.label.value, 0) + 1
        return cls(
            id=check.id,
            created_at=check.created_at,
            status=check.status,
            claims=len(check.claims),
            verdicts=counts,
            official_flags=sum(f.basis is FlagBasis.VERIFIED_RULE for f in check.red_flags),
            potential_concerns=sum(f.basis is FlagBasis.POTENTIAL_CONCERN for f in check.red_flags),
        )


class CreatorView(_Out):
    handle: str
    checks: int
    totals: dict[str, int]
    recent: list[CheckSummary]
    note: str = (
        "This summarises checks of individual claims. It is not a judgement of the person. The "
        "accountability profile and Claim Ledger arrive in a later version."
    )


class RuleSourceRef(_Out):
    id: str
    title: str
    url: str
    reference_number: str | None = None
    published_on: str | None = None
    verification_level: str


class RuleEntry(_Out):
    id: str
    kind: str
    title: str
    what: str
    why: str
    takeaway: str
    provision: str | None = None
    sources: list[RuleSourceRef]


class RulebookResponse(_Out):
    rules: list[RuleEntry]
    sources: list[RegulatorySource]


class GlossaryTerm(_Out):
    term: str
    definition: str


class Health(_Out):
    status: Literal["ok"] = "ok"
    version: str
    llm_provider: str
    search_provider: str
    queue_mode: str

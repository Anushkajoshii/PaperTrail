"""Core data models: what a check, a claim, evidence, a verdict and a red flag look like.

These models are the contract between the AI pipeline, the API and the UI. Several product rules
are enforced here, so no part of the system (including the LLM) can bypass them:

* A verdict of "supported" or "contradicted" must cite evidence with the matching stance.
* A red flag labelled ``verified_rule`` must cite an official SEBI source (sebi.gov.in) that is
  attached to the check. Anything else is a ``potential_concern``.
* Confidence (in the assessment) is kept separate from certainty (which we never claim).

See docs/adr/003-claims-not-people-verdict-language.md.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Self
from urllib.parse import urlparse
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

# --------------------------------------------------------------------------------------------
# Standard notices: shown with every result.
# --------------------------------------------------------------------------------------------

NOT_FINANCIAL_ADVICE = (
    "PaperTrail is not financial advice. It assesses specific claims against available "
    "evidence and does not recommend buying or selling any security."
)
REGISTRATION_NOT_ENDORSEMENT = (
    "SEBI registration means a person or firm met SEBI's eligibility requirements. It does not "
    "mean SEBI endorses, approves or guarantees their advice or returns."
)
CONFIDENCE_NOT_CERTAINTY = (
    "Confidence describes how strongly the evidence we found backs our assessment. It is not "
    "a guarantee that a claim is true or false."
)
STANDARD_NOTICES: tuple[str, ...] = (
    NOT_FINANCIAL_ADVICE,
    REGISTRATION_NOT_ENDORSEMENT,
    CONFIDENCE_NOT_CERTAINTY,
)

OFFICIAL_SEBI_HOSTS = frozenset({"sebi.gov.in", "www.sebi.gov.in", "investor.sebi.gov.in"})


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(UTC)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------------------------


class Language(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hinglish"


class InputKind(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    ARTICLE_URL = "article_url"


class ClaimType(StrEnum):
    PAST_PERFORMANCE = "past_performance"  # "This stock gave 300% last year"
    RETURN_PROMISE = "return_promise"  # "You will earn 5% every month"
    STOCK_CALL = "stock_call"  # "Buy X, target ₹500 in 3 months" (tracked by the Ledger)
    MARKET_FACT = "market_fact"  # "Nifty hit an all-time high on ..."
    COMPANY_FACT = "company_fact"  # "Company X's profit doubled in FY24"
    CREDENTIAL = "credential"  # "I am a SEBI-registered adviser"
    OTHER = "other"


class SourceType(StrEnum):
    REGULATOR = "regulator"
    EXCHANGE = "exchange"
    COMPANY_FILING = "company_filing"
    DATA_PROVIDER = "data_provider"
    REPUTABLE_NEWS = "reputable_news"
    BLOG = "blog"
    SOCIAL = "social"
    OTHER = "other"


class Stance(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"  # relevant background that neither confirms nor refutes


class VerdictLabel(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    MISLEADING = "misleading"
    NOT_VERIFIABLE = "not_verifiable"


class ConfidenceBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FlagBasis(StrEnum):
    VERIFIED_RULE = "verified_rule"  # quotes a curated official SEBI source
    POTENTIAL_CONCERN = "potential_concern"  # AI observation; never presented as a violation


class RedFlagKind(StrEnum):
    GUARANTEED_RETURNS = "guaranteed_returns"
    MISLEADING_PERFORMANCE = "misleading_performance"
    UNREGISTERED_ADVICE = "unregistered_advice"
    MISSING_DISCLAIMER = "missing_disclaimer"
    UNCONFIRMED_REGISTRATION_CLAIM = "unconfirmed_registration_claim"
    TIP_GROUP_SOLICITATION = "tip_group_solicitation"
    PRESSURE_TACTICS = "pressure_tactics"
    LIVE_PRICE_EDUCATION = "live_price_education"
    OTHER = "other"


class SebiDocType(StrEnum):
    REGULATION = "regulation"
    CIRCULAR = "circular"
    MASTER_CIRCULAR = "master_circular"
    GUIDELINE = "guideline"
    INVESTOR_AWARENESS = "investor_awareness"
    PRESS_RELEASE = "press_release"


class RegistrationStatus(StrEnum):
    REGISTERED_IA = "registered_investment_adviser"
    REGISTERED_RA = "registered_research_analyst"
    REGISTERED_IA_AND_RA = "registered_investment_adviser_and_research_analyst"
    NOT_FOUND = "not_found"  # not found in our snapshot; NOT proof of being unregistered
    NOT_CHECKED = "not_checked"


class CheckStatus(StrEnum):
    QUEUED = "queued"
    TRANSCRIBING = "transcribing"
    EXTRACTING = "extracting"
    RESEARCHING = "researching"
    JUDGING = "judging"
    CHECKING_RULEBOOK = "checking_rulebook"
    COMPLETED = "completed"
    FAILED = "failed"


# Plain-language descriptions used by the API and UI (tooltips, progress screen).
VERDICT_DESCRIPTIONS: dict[VerdictLabel, str] = {
    VerdictLabel.SUPPORTED: "Reliable sources agree with this claim.",
    VerdictLabel.CONTRADICTED: "Reliable sources say the opposite of this claim.",
    VerdictLabel.MISLEADING: "Partly true, but important missing context changes its meaning.",
    VerdictLabel.NOT_VERIFIABLE: (
        "We could not find enough reliable evidence either way. This is not an accusation."
    ),
}

STATUS_DESCRIPTIONS: dict[CheckStatus, str] = {
    CheckStatus.QUEUED: "Your check is in line and will start shortly.",
    CheckStatus.TRANSCRIBING: "Turning speech into text.",
    CheckStatus.EXTRACTING: "Finding the statements that can be fact-checked.",
    CheckStatus.RESEARCHING: "Looking for evidence from trustworthy sources.",
    CheckStatus.JUDGING: "Weighing the evidence for and against each claim.",
    CheckStatus.CHECKING_RULEBOOK: "Comparing statements with official SEBI rules and guidance.",
    CheckStatus.COMPLETED: "Done. Your results are ready.",
    CheckStatus.FAILED: "Something went wrong. No partial verdicts are shown.",
}


# --------------------------------------------------------------------------------------------
# Claims and evidence
# --------------------------------------------------------------------------------------------


class Claim(_Model):
    """One checkable statement of fact found in the content."""

    id: str = Field(default_factory=lambda: _new_id("clm"))
    text: str = Field(min_length=3, description="The claim restated clearly in English.")
    quote: str = Field(min_length=1, description="The exact words used in the content.")
    claim_type: ClaimType
    language: Language = Language.ENGLISH
    timestamp_seconds: float | None = Field(
        default=None, ge=0, description="Where in the video or audio the claim was made."
    )
    tickers: list[str] = Field(default_factory=list, description="NSE/BSE symbols mentioned.")
    why_checkable: str | None = Field(
        default=None, description="Plain-language reason this statement can be fact-checked."
    )


class TranscriptSegment(_Model):
    """A timed piece of a transcript (from speech-to-text), used to timestamp claims."""

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str


class SourceQuality(_Model):
    """How much weight a source deserves. Each score is between 0 and 1."""

    reliability: float = Field(ge=0, le=1, description="How trustworthy this type of source is.")
    recency: float = Field(ge=0, le=1, description="How recent the source is, for this claim.")
    relevance: float = Field(ge=0, le=1, description="How directly it addresses this claim.")

    @property
    def overall(self) -> float:
        """Weighted score. Reliability matters most; an irrelevant source is worth little."""
        return round(0.5 * self.reliability + 0.2 * self.recency + 0.3 * self.relevance, 3)


class Evidence(_Model):
    """A quoted passage from a source that relates to a claim."""

    id: str = Field(default_factory=lambda: _new_id("evd"))
    claim_id: str
    url: HttpUrl
    title: str
    publisher: str | None = None
    published_at: date | None = None
    source_type: SourceType
    snippet: str = Field(min_length=1, description="The exact passage relied on (quoted data).")
    stance: Stance
    quality: SourceQuality


class Explanation(_Model):
    """Why the system reached its verdict, in plain language."""

    summary: str = Field(min_length=1, description="One or two sentences for a non-expert.")
    reasoning: list[str] = Field(
        default_factory=list, description="The key steps of reasoning, in order."
    )
    could_not_verify: list[str] = Field(
        default_factory=list, description="Parts of the claim we could not check, and why."
    )


class Verdict(_Model):
    """The assessment of one claim."""

    claim_id: str
    label: VerdictLabel
    confidence: float = Field(
        ge=0, le=1, description="Confidence in this assessment. This is NOT certainty of truth."
    )
    explanation: Explanation
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    context_evidence_ids: list[str] = Field(default_factory=list)

    @property
    def confidence_band(self) -> ConfidenceBand:
        if self.confidence >= 0.75:
            return ConfidenceBand.HIGH
        if self.confidence >= 0.45:
            return ConfidenceBand.MEDIUM
        return ConfidenceBand.LOW

    @property
    def description(self) -> str:
        return VERDICT_DESCRIPTIONS[self.label]

    @property
    def cited_evidence_ids(self) -> list[str]:
        return [
            *self.supporting_evidence_ids,
            *self.contradicting_evidence_ids,
            *self.context_evidence_ids,
        ]

    @model_validator(mode="after")
    def _verdict_needs_matching_evidence(self) -> Self:
        if self.label is VerdictLabel.SUPPORTED and not self.supporting_evidence_ids:
            raise ValueError("a 'supported' verdict must cite at least one supporting source")
        if self.label is VerdictLabel.CONTRADICTED and not self.contradicting_evidence_ids:
            raise ValueError("a 'contradicted' verdict must cite at least one contradicting source")
        if self.label is VerdictLabel.MISLEADING and not self.cited_evidence_ids:
            raise ValueError("a 'misleading' verdict must cite the evidence giving missing context")
        return self


# --------------------------------------------------------------------------------------------
# SEBI rulebook and registration
# --------------------------------------------------------------------------------------------


class VerificationLevel(StrEnum):
    FULL_TEXT = "full_text"  # we read the official document itself
    OFFICIAL_LISTING = "official_listing"  # SEBI's page confirms title/date; text not reviewed
    QUOTED_IN_SEBI_ORDERS = "quoted_in_sebi_orders"  # wording taken from SEBI's own orders


class Provision(_Model):
    """A specific clause, paraphrased in plain language (never invented)."""

    ref: str = Field(description="e.g. 'Regulation 3(1)'")
    summary: str


class RegulatorySource(_Model):
    """An official SEBI document from the curated rulebook registry."""

    id: str = Field(description="Stable registry id, e.g. 'sebi-ia-regs-2013'.")
    title: str
    doc_type: SebiDocType
    url: HttpUrl
    reference_number: str | None = Field(default=None, description="Circular or notification no.")
    published_on: date | None = Field(default=None, description="None if the page shows no date.")
    effective_from: date | None = None
    amended_up_to: date | None = Field(default=None, description="For consolidated texts.")
    updated_on: date | None = Field(default=None, description="For circulars revised later.")
    summary: str = Field(description="Plain-language summary of what the document says.")
    key_points: list[str] = Field(default_factory=list)
    provisions: list[Provision] = Field(default_factory=list)
    verified_on: date | None = Field(default=None, description="When we last checked the source.")
    verification_level: VerificationLevel = VerificationLevel.FULL_TEXT
    verification_note: str | None = None

    @model_validator(mode="after")
    def _must_be_official_sebi(self) -> Self:
        host = (urlparse(str(self.url)).hostname or "").lower()
        if host not in OFFICIAL_SEBI_HOSTS:
            raise ValueError(f"regulatory sources must be hosted on sebi.gov.in, got '{host}'")
        if self.effective_from and self.published_on and self.effective_from < self.published_on:
            # Allowed in rare cases (retrospective effect) but almost always a data-entry error.
            raise ValueError("effective_from is earlier than published_on; check the source")
        return self


class RedFlag(_Model):
    """A statement that official SEBI material warns about, explained for a layperson."""

    id: str = Field(default_factory=lambda: _new_id("flg"))
    kind: RedFlagKind
    basis: FlagBasis
    detected_text: str = Field(min_length=1, description="The exact words that were flagged.")
    claim_id: str | None = None
    what_was_detected: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    investor_takeaway: str = Field(
        min_length=1, description="What an ordinary investor should know."
    )
    rule_source_ids: list[str] = Field(
        default_factory=list, description="Ids of RegulatorySource entries this flag relies on."
    )
    relevant_provision: str | None = Field(
        default=None, description="Exact regulation/clause, only when quoted from the source."
    )

    @model_validator(mode="after")
    def _verified_rule_needs_source(self) -> Self:
        if self.basis is FlagBasis.VERIFIED_RULE and not self.rule_source_ids:
            raise ValueError("a 'verified_rule' flag must cite at least one official SEBI source")
        if self.basis is FlagBasis.POTENTIAL_CONCERN and self.relevant_provision:
            raise ValueError(
                "a 'potential_concern' must not name a specific provision; "
                "only verified rules quote provisions"
            )
        return self

    @property
    def label(self) -> str:
        if self.basis is FlagBasis.VERIFIED_RULE:
            return "Official SEBI rule or guidance"
        return "Potential concern (AI observation, not a finding of violation)"


class SebiRegistration(_Model):
    """Result of looking a creator up in SEBI's list of registered intermediaries."""

    status: RegistrationStatus = RegistrationStatus.NOT_CHECKED
    matched_name: str | None = None
    registration_numbers: list[str] = Field(default_factory=list)
    registry_snapshot_date: date | None = None
    source_url: HttpUrl | None = None
    note: str = REGISTRATION_NOT_ENDORSEMENT

    @property
    def is_registered(self) -> bool:
        return self.status in {
            RegistrationStatus.REGISTERED_IA,
            RegistrationStatus.REGISTERED_RA,
            RegistrationStatus.REGISTERED_IA_AND_RA,
        }


# --------------------------------------------------------------------------------------------
# The check: one end-to-end analysis of one piece of content
# --------------------------------------------------------------------------------------------


class CheckInput(_Model):
    kind: InputKind
    text: str | None = Field(default=None, description="Pasted text (kind=text).")
    url: HttpUrl | None = Field(default=None, description="Article URL (kind=article_url).")
    upload_key: str | None = Field(default=None, description="Storage key of an uploaded file.")
    creator_handle: str | None = Field(default=None, description="e.g. '@somecreator'.")
    creator_name: str | None = None
    language_hint: Language | None = None

    @model_validator(mode="after")
    def _payload_matches_kind(self) -> Self:
        required = {
            InputKind.TEXT: ("text", self.text),
            InputKind.ARTICLE_URL: ("url", self.url),
            InputKind.VIDEO: ("upload_key", self.upload_key),
            InputKind.AUDIO: ("upload_key", self.upload_key),
        }[self.kind]
        if not required[1]:
            raise ValueError(f"input kind '{self.kind}' requires '{required[0]}'")
        return self


class Check(_Model):
    id: str = Field(default_factory=lambda: _new_id("chk"))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    status: CheckStatus = CheckStatus.QUEUED
    input: CheckInput
    detected_language: Language | None = None
    transcript: str | None = None
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    verdicts: list[Verdict] = Field(default_factory=list)
    red_flags: list[RedFlag] = Field(default_factory=list)
    regulatory_sources: list[RegulatorySource] = Field(default_factory=list)
    registration: SebiRegistration = Field(default_factory=SebiRegistration)
    error: str | None = None

    @property
    def notices(self) -> tuple[str, ...]:
        return STANDARD_NOTICES

    @property
    def status_description(self) -> str:
        return STATUS_DESCRIPTIONS[self.status]

    @model_validator(mode="after")
    def _references_are_consistent(self) -> Self:
        claim_ids = {c.id for c in self.claims}
        evidence_by_id = {e.id: e for e in self.evidence}
        source_ids = {s.id for s in self.regulatory_sources}

        for ev in self.evidence:
            if ev.claim_id not in claim_ids:
                raise ValueError(f"evidence {ev.id} refers to unknown claim {ev.claim_id}")

        for v in self.verdicts:
            if v.claim_id not in claim_ids:
                raise ValueError(f"verdict refers to unknown claim {v.claim_id}")
            for ids, stance in (
                (v.supporting_evidence_ids, Stance.SUPPORTS),
                (v.contradicting_evidence_ids, Stance.CONTRADICTS),
                (v.context_evidence_ids, Stance.CONTEXT),
            ):
                for eid in ids:
                    ev = evidence_by_id.get(eid)
                    if ev is None:
                        raise ValueError(f"verdict cites unknown evidence {eid}")
                    if ev.claim_id != v.claim_id:
                        raise ValueError(f"evidence {eid} belongs to a different claim")
                    if ev.stance is not stance:
                        raise ValueError(f"evidence {eid} has stance '{ev.stance}', not '{stance}'")

        for f in self.red_flags:
            missing = [sid for sid in f.rule_source_ids if sid not in source_ids]
            if missing:
                raise ValueError(f"red flag {f.id} cites sources not attached to check: {missing}")
            if f.claim_id is not None and f.claim_id not in claim_ids:
                raise ValueError(f"red flag {f.id} refers to unknown claim {f.claim_id}")

        if self.status is CheckStatus.FAILED and not self.error:
            raise ValueError("a failed check must include an error message")
        return self

    def verdict_for(self, claim_id: str) -> Verdict | None:
        return next((v for v in self.verdicts if v.claim_id == claim_id), None)

    def evidence_for(self, claim_id: str) -> list[Evidence]:
        return [e for e in self.evidence if e.claim_id == claim_id]

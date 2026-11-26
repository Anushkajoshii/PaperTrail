"""Deterministic red-flag rules, each tied to verified official SEBI sources.

Every rule answers four questions in plain language:
  what_was_detected / why_it_matters / investor_takeaway / which official source applies

Language principles (ADR-003, ADR-008):
* We describe what was *said* and what SEBI's material says about it. We never say a person
  "violated" a rule: only SEBI or a court can decide that.
* "Not found in our copy of SEBI's register" is never presented as "unregistered".
* Rules only cite sources in the curated registry (``sources.py``). The engine checks this at
  import time, so a typo in a source id fails the tests, not the user.

Rules that need a fact we cannot see (e.g. whether price data was from the last 30 days) are
worded conditionally ("this may matter if...").
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from papertrail.models import (
    Claim,
    ClaimType,
    FlagBasis,
    RedFlag,
    RedFlagKind,
    RegistrationStatus,
    RegulatorySource,
    SebiRegistration,
)
from papertrail.rulebook.sources import get_source, get_sources
from papertrail.text import normalize_for_match, split_sentences

SEBI_REGISTER_URL = "https://www.sebi.gov.in/intermediaries.html"
SEBI_MI_PORTAL_URL = "https://mi.sebi.gov.in/"


def _rx(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)


# --- Patterns (English, Hinglish, Hindi) ----------------------------------------------------
# Hindi patterns avoid \b: Devanagari vowel signs are not "word" characters for Python's re.

GUARANTEE = _rx(
    r"\bguarantee(d|s)?\b",
    r"\bassured\s+(returns?|profits?|income|gains?)\b",
    r"\brisk[- ]?free\b",
    r"\bno[- ]?loss\b",
    r"\bzero[- ]?risk\b",
    r"\bsure[- ]?shot\b",
    r"\bpakk[ae]\s+(profit|return|munafa|double|kamai)",
    r"\b100\s?%\s+(safe|sure|profit|guaranteed)\b",
    r"\bfixed\s+(monthly\s+)?(returns?|income|profit)\b",
    r"\b(paisa|money)\s+double\b",
    r"\bdouble\s+your\s+(money|capital|investment)\b",
    r"\bgaaranti\b",
    "गारंटी",
    "पक्का (मुनाफ़ा|मुनाफा|रिटर्न|फायदा)",
    "निश्चित (रिटर्न|मुनाफ़ा|मुनाफा)",
    "जोखिम[- ]?मुक्त",
)

PERFORMANCE = _rx(
    r"\b(gave|given|returned|delivered|diya|diye|de\s+chuka)\b[^.!?\n]{0,40}\d+(\.\d+)?\s?%",
    r"\d+(\.\d+)?\s?%\s*(returns?|profit|munafa|gain)",
    r"\b(my|our|mere|hamare)\s+(students?|clients?|members?|subscribers?|followers?)\b"
    r"[^.!?\n]{0,30}\b(made|earned|kamaye?|profit)",
    r"\b(accuracy|success\s+rate|hit\s+rate|win\s+rate)\b[^.!?\n]{0,15}\d+\s?%",
    r"\d+\s?%\s*(accuracy|success|hit\s+rate|win\s+rate)",
    r"\bprofit\s+screenshots?\b",
    r"\d+\s?%\s*(रिटर्न|मुनाफ़ा|मुनाफा)",
)

RECOMMENDATION = _rx(
    r"\b(buy|sell|accumulate|exit|short)\b[^.!?\n]{0,50}"
    r"(\btarget\b|\btgt\b|\bstop[- ]?loss\b|\bsl\b|₹\s?\d|\brs\.?\s?\d)",
    r"\btarget\b[^.!?\n]{0,25}(₹\s?\d|\brs\.?\s?\d|\d{2,})",
    r"\b(kharid|khareed|bech)\w*\b[^.!?\n]{0,40}(target|₹\s?\d|\d{2,})",
    r"\bstop[- ]?loss\b[^.!?\n]{0,20}\d",
    "(खरीद|बेच)[^।\n]{0,40}(टारगेट|लक्ष्य|₹)",
)

REGISTRATION_CLAIM = _rx(
    r"\bsebi[- ]?(registered|regd\.?|certified|approved)\b",
    r"\bregistered\s+(with\s+sebi|investment\s+advis[eo]rs?|research\s+analysts?)\b",
    r"\bsebi\s+(ria|ra)\b",
    r"\b(ria|ra)\s+registration\b",
    r"\bregistration\s+(no|number)\b",
    "सेबी (रजिस्टर्ड|पंजीकृत)",
)

TIP_GROUP = _rx(
    r"\b(telegram|whats\s?app|discord)\b",
    r"\b(vip|premium|paid|private|exclusive|inner\s+circle)\s+(group|channel|community|club)\b",
    r"\bjoin\s+(my|our|the)\s+(group|channel|community|club)\b",
    r"\binstitutional\s+trading\s+group\b",
    r"\binvestment\s+club\b",
    "टेलीग्राम",
    "व्हाट्सऐप",
)

EDUCATION_FRAMING = _rx(
    r"\b(for\s+)?educational?\s+purposes?(\s+only)?\b",
    r"\beducation(al)?\s+only\b",
    r"\b(sirf|just|only)\s+(for\s+)?education\b",
    r"\bnot\s+(a\s+)?(buy|sell|stock)?\s*recommendations?\b",
    r"\bnot\s+(financial|investment)\s+advice\b",
    "शिक्षा के (उद्देश्य|लिए)",
)

PRESSURE = _rx(
    r"\b(buy|join|invest|enrol+|register|subscribe)\s+(now|today|immediately|right\s+away)\b",
    r"\bbefore\s+(monday|tomorrow|it'?s\s+too\s+late|the\s+market\s+opens)\b",
    r"\blast\s+chance\b",
    r"\blimited\s+(seats|slots|spots|offer|period|time)\b",
    r"\bonly\s+\d+\s+(seats|slots|spots)\s+left\b",
    r"\bhurry\b",
    r"\bdon'?t\s+miss\b",
    r"\boffer\s+ends\b",
    r"\bjaldi\b",
    r"\babhi\s+(kharid|khareed|join|le\s+lo|invest)",
    r"\bwarna\s+pacht",
    "अभी (खरीदें|खरीदो|जुड़ें)",
    "जल्दी (करें|करो)",
)


# --- Rule definitions -----------------------------------------------------------------------


@dataclass(frozen=True)
class RuleContext:
    transcript: str
    claims: list[Claim]
    registration: SebiRegistration
    creator_name: str | None = None

    @property
    def has_recommendation(self) -> bool:
        return any(c.claim_type is ClaimType.STOCK_CALL for c in self.claims) or bool(
            RECOMMENDATION.search(self.transcript)
        )


@dataclass(frozen=True)
class FlagRule:
    id: str
    kind: RedFlagKind
    title: str  # short heading for the UI rulebook page
    pattern: re.Pattern[str]
    source_ids: tuple[str, ...]
    what: str
    why: str | Callable[[RuleContext], str]
    takeaway: str
    provision: str | None = None
    applies: Callable[[RuleContext], bool] = lambda ctx: True
    max_hits: int = 2

    def why_for(self, ctx: RuleContext) -> str:
        return self.why(ctx) if callable(self.why) else self.why


def _not_registered(ctx: RuleContext) -> bool:
    return not ctx.registration.is_registered


def _registration_status_text(ctx: RuleContext) -> str:
    if ctx.registration.status is RegistrationStatus.NOT_FOUND:
        return (
            "We could not find this creator in our copy of SEBI's register. That is not proof "
            "they are unregistered: names can be written differently and our copy can be out of "
            "date."
        )
    return (
        "We have not been able to check this creator's registration yet (no name or "
        "registration number was available)."
    )


RULES: tuple[FlagRule, ...] = (
    FlagRule(
        id="guaranteed-returns",
        kind=RedFlagKind.GUARANTEED_RETURNS,
        title="Promises of guaranteed or risk-free returns",
        pattern=GUARANTEE,
        source_ids=("sebi-pr-22-2025-social-media", "sebi-investor-spot-a-scam"),
        what="A promise of guaranteed, assured or risk-free returns.",
        why=(
            "SEBI's investor guidance says all securities investments carry some risk, and "
            "SEBI's caution on social-media frauds lists promises of assured or risk-free "
            "returns as a common trick."
        ),
        takeaway=(
            "No one can guarantee returns from the stock market. Treat any such promise as a "
            "warning sign, whoever makes it."
        ),
    ),
    FlagRule(
        id="performance-claims",
        kind=RedFlagKind.MISLEADING_PERFORMANCE,
        title="Claims of returns, accuracy or past performance",
        pattern=PERFORMANCE,
        source_ids=("sebi-circular-2025-11-association", "sebi-pr-22-2025-social-media"),
        provision="Regulation 16A, SEBI (Intermediaries) Regulations, 2008",
        what="A claim about returns or performance (for example '300% returns' or '90% accuracy').",
        why=(
            "Under SEBI's 2024 rules, making claims of returns or performance about securities "
            "without SEBI's permission is one of two 'prohibited activities' that SEBI-registered "
            "firms may not be associated with. SEBI also warns about misleading testimonials. "
            "A single impressive number is easy to cherry-pick."
        ),
        takeaway=(
            "Ask for a complete, verifiable track record, not one good number. PaperTrail checks "
            "the number itself in the claims section."
        ),
    ),
    FlagRule(
        id="advice-without-confirmed-registration",
        kind=RedFlagKind.UNREGISTERED_ADVICE,
        title="Specific stock recommendations without a confirmed SEBI registration",
        pattern=RECOMMENDATION,
        source_ids=(
            "sebi-ra-regs-2014",
            "sebi-ia-regs-2013",
            "sebi-circular-2025-11-association",
        ),
        provision="Regulation 3(1), SEBI (Research Analysts) Regulations, 2014",
        what="A specific buy/sell recommendation or price target for a security.",
        why=lambda ctx: (
            "SEBI requires anyone who publishes stock recommendations as a research analyst, "
            "including on the internet, to be registered (and anyone giving investment advice to "
            "be a registered investment adviser). " + _registration_status_text(ctx)
        ),
        takeaway=(
            "Before acting on a stock tip, look the person up on SEBI's register "
            f"({SEBI_REGISTER_URL}). Registered research analysts have a number starting with "
            "INH, investment advisers with INA."
        ),
        applies=_not_registered,
    ),
    FlagRule(
        id="unconfirmed-registration-claim",
        kind=RedFlagKind.UNCONFIRMED_REGISTRATION_CLAIM,
        title="Claims of SEBI registration we could not confirm",
        pattern=REGISTRATION_CLAIM,
        source_ids=("sebi-pr-22-2025-social-media", "sebi-pr-112-2016-registered-only"),
        what="The speaker says they are SEBI-registered, but we could not confirm it.",
        why=lambda ctx: (
            "SEBI has warned that some people falsely claim SEBI registration or show fake SEBI "
            "certificates, and advises checking registration on SEBI's website. "
            + _registration_status_text(ctx)
        ),
        takeaway=(
            f"Search the name and registration number on SEBI's register ({SEBI_REGISTER_URL}) "
            "and make sure they match the person you are dealing with."
        ),
        applies=_not_registered,
        max_hits=1,
    ),
    FlagRule(
        id="private-tip-groups",
        kind=RedFlagKind.TIP_GROUP_SOLICITATION,
        title="Invitations to private Telegram, WhatsApp or 'VIP' groups",
        pattern=TIP_GROUP,
        source_ids=("sebi-pr-22-2025-social-media",),
        what="An invitation to a private Telegram/WhatsApp group or a 'VIP' or premium channel.",
        why=(
            "SEBI has warned that scamsters lure investors into private WhatsApp and Telegram "
            "groups (named things like 'VIP group' or 'Investment Club') through social-media "
            "posts."
        ),
        takeaway=(
            "Be very careful with tips shared in private groups. If something goes wrong with an "
            "unregistered entity, SEBI's investor-protection mechanisms such as SCORES are not "
            f"available. You can report such groups on SEBI's portal ({SEBI_MI_PORTAL_URL})."
        ),
    ),
    FlagRule(
        id="education-label-with-stock-calls",
        kind=RedFlagKind.LIVE_PRICE_EDUCATION,
        title="'For education only' content that names stocks with targets",
        pattern=EDUCATION_FRAMING,
        source_ids=("sebi-circular-2025-11-association",),
        provision="Annexure A, FAQ 8 of circular SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2025/11",
        what=(
            "The content says it is for education (or 'not advice') but also names a specific "
            "stock with a target or a buy/sell view."
        ),
        why=(
            "SEBI's clarification says a person engaged solely in education should not use "
            "market price data of the preceding 30 days to name a security while indicating its "
            "future price, advice or a recommendation (the period was three months before 8 May "
            "2026). This may matter if recent prices were used. A disclaimer does not by itself "
            "turn a recommendation into education."
        ),
        takeaway=(
            "Treat a named stock with a target as a recommendation, whatever the label says, "
            "and check whether the person is registered."
        ),
        applies=lambda ctx: ctx.has_recommendation,
        max_hits=1,
    ),
    FlagRule(
        id="pressure-tactics",
        kind=RedFlagKind.PRESSURE_TACTICS,
        title="Pressure to act immediately",
        pattern=PRESSURE,
        source_ids=("sebi-investor-spot-a-scam",),
        what="Pressure to buy, join or pay quickly.",
        why="SEBI's investor guidance lists pressure to decide immediately as a warning sign.",
        takeaway="Real opportunities do not disappear in hours. Take your time and check first.",
        max_hits=1,
    ),
)


def _validate_rules() -> None:
    ids = [r.id for r in RULES]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate rule ids")
    for rule in RULES:
        for sid in rule.source_ids:
            get_source(sid)  # raises UnknownSourceError for typos


_validate_rules()


# --- Engine ---------------------------------------------------------------------------------


@dataclass
class RulebookResult:
    flags: list[RedFlag] = field(default_factory=list)
    sources: list[RegulatorySource] = field(default_factory=list)

    def counts_by_kind(self) -> dict[RedFlagKind, int]:
        out: dict[RedFlagKind, int] = {}
        for f in self.flags:
            out[f.kind] = out.get(f.kind, 0) + 1
        return out


def _claim_for(sentence: str, claims: list[Claim]) -> str | None:
    s = normalize_for_match(sentence)
    for c in claims:
        q = normalize_for_match(c.quote)
        if q and (q in s or s in q):
            return c.id
    return None


def apply_rules(
    transcript: str,
    claims: list[Claim],
    registration: SebiRegistration,
    *,
    creator_name: str | None = None,
) -> RulebookResult:
    ctx = RuleContext(transcript, claims, registration, creator_name)
    sentences = split_sentences(transcript)
    result = RulebookResult()
    cited: list[str] = []
    for rule in RULES:
        if not rule.applies(ctx):
            continue
        hits = [s for s in sentences if rule.pattern.search(s)][: rule.max_hits]
        for sentence in hits:
            result.flags.append(
                RedFlag(
                    kind=rule.kind,
                    basis=FlagBasis.VERIFIED_RULE,
                    detected_text=sentence,
                    claim_id=_claim_for(sentence, claims),
                    what_was_detected=rule.what,
                    why_it_matters=rule.why_for(ctx),
                    investor_takeaway=rule.takeaway,
                    rule_source_ids=list(rule.source_ids),
                    relevant_provision=rule.provision,
                )
            )
            cited.extend(rule.source_ids)
    result.sources = get_sources(cited)
    return result


def rule_catalog() -> list[dict]:
    """Every rule with its explanation and sources, for the in-app SEBI rulebook page."""
    catalog = []
    placeholder = RuleContext("", [], SebiRegistration(status=RegistrationStatus.NOT_FOUND))
    for rule in RULES:
        catalog.append(
            {
                "id": rule.id,
                "kind": rule.kind.value,
                "title": rule.title,
                "what": rule.what,
                "why": rule.why_for(placeholder),
                "takeaway": rule.takeaway,
                "provision": rule.provision,
                "sources": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "url": str(s.url),
                        "reference_number": s.reference_number,
                        "published_on": s.published_on.isoformat() if s.published_on else None,
                        "verification_level": s.verification_level.value,
                    }
                    for s in get_sources(list(rule.source_ids))
                ],
            }
        )
    return catalog

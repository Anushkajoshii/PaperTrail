"""How much weight a source deserves: reliability, recency and relevance, each from 0 to 1.

* **Reliability** depends on the *type* of source: regulators and exchanges first, established
  news next, blogs and social media last. It is a transparent lookup table, not a model, so every
  score can be explained (see ADR-007).
* **Recency** decays with age, at a rate that depends on the claim. A registration status from 2
  years ago is stale; an index level from 2024 is still a fact.
* **Relevance** is a fast lexical score: does the passage mention the claim's key terms, tickers
  and numbers? The LLM judge decides what the evidence *means*; this only ranks what it reads.

Each score also gets a plain-English label for the UI (``describe_quality``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from papertrail.models import Claim, ClaimType, SourceQuality, SourceType
from papertrail.text import normalize_for_match, split_sentences
from papertrail.tools.search import registrable_domain


@dataclass(frozen=True)
class SourceProfile:
    source_type: SourceType
    reliability: float
    label: str  # shown to users, e.g. "Official regulator"


_TYPE_DEFAULTS: dict[SourceType, tuple[float, str]] = {
    SourceType.REGULATOR: (0.98, "Official regulator or government body"),
    SourceType.EXCHANGE: (0.97, "Stock exchange"),
    SourceType.COMPANY_FILING: (0.92, "Official company filing"),
    SourceType.DATA_PROVIDER: (0.85, "Financial data provider"),
    SourceType.REPUTABLE_NEWS: (0.80, "Established financial news outlet"),
    SourceType.OTHER: (0.50, "Website of unknown reliability"),
    SourceType.BLOG: (0.35, "Blog or personal website"),
    SourceType.SOCIAL: (0.15, "Social media"),
}

DOMAIN_TYPES: dict[str, SourceType] = {
    # Regulators and government
    "sebi.gov.in": SourceType.REGULATOR,
    "rbi.org.in": SourceType.REGULATOR,
    "mca.gov.in": SourceType.REGULATOR,
    "pib.gov.in": SourceType.REGULATOR,
    "incometax.gov.in": SourceType.REGULATOR,
    "pfrda.org.in": SourceType.REGULATOR,
    "irdai.gov.in": SourceType.REGULATOR,
    "cybercrime.gov.in": SourceType.REGULATOR,
    # Exchanges and depositories
    "nseindia.com": SourceType.EXCHANGE,
    "bseindia.com": SourceType.EXCHANGE,
    "mcxindia.com": SourceType.EXCHANGE,
    "nsdl.co.in": SourceType.EXCHANGE,
    "cdslindia.com": SourceType.EXCHANGE,
    # Filings
    "nsearchives.nseindia.com": SourceType.COMPANY_FILING,
    # Data providers and industry bodies
    "amfiindia.com": SourceType.DATA_PROVIDER,
    "valueresearchonline.com": SourceType.DATA_PROVIDER,
    "morningstar.in": SourceType.DATA_PROVIDER,
    "screener.in": SourceType.DATA_PROVIDER,
    "tickertape.in": SourceType.DATA_PROVIDER,
    "trendlyne.com": SourceType.DATA_PROVIDER,
    "niftyindices.com": SourceType.DATA_PROVIDER,
    # News
    "economictimes.indiatimes.com": SourceType.REPUTABLE_NEWS,
    "livemint.com": SourceType.REPUTABLE_NEWS,
    "business-standard.com": SourceType.REPUTABLE_NEWS,
    "thehindubusinessline.com": SourceType.REPUTABLE_NEWS,
    "financialexpress.com": SourceType.REPUTABLE_NEWS,
    "moneycontrol.com": SourceType.REPUTABLE_NEWS,
    "ndtvprofit.com": SourceType.REPUTABLE_NEWS,
    "cnbctv18.com": SourceType.REPUTABLE_NEWS,
    "reuters.com": SourceType.REPUTABLE_NEWS,
    "bloomberg.com": SourceType.REPUTABLE_NEWS,
    "thehindu.com": SourceType.REPUTABLE_NEWS,
    "indianexpress.com": SourceType.REPUTABLE_NEWS,
    "hindustantimes.com": SourceType.REPUTABLE_NEWS,
    "zeebiz.com": SourceType.REPUTABLE_NEWS,
    # Blogs
    "medium.com": SourceType.BLOG,
    "substack.com": SourceType.BLOG,
    "blogspot.com": SourceType.BLOG,
    "wordpress.com": SourceType.BLOG,
    # Social
    "youtube.com": SourceType.SOCIAL,
    "instagram.com": SourceType.SOCIAL,
    "facebook.com": SourceType.SOCIAL,
    "x.com": SourceType.SOCIAL,
    "twitter.com": SourceType.SOCIAL,
    "t.me": SourceType.SOCIAL,
    "reddit.com": SourceType.SOCIAL,
    "quora.com": SourceType.SOCIAL,
    "linkedin.com": SourceType.SOCIAL,
    # Offline demo data (see tools/data/offline_search.json): clearly labelled, never real.
    "regulator.demo.test": SourceType.REGULATOR,
    "exchange.demo.test": SourceType.EXCHANGE,
    "filings.demo.test": SourceType.COMPANY_FILING,
    "news.demo.test": SourceType.REPUTABLE_NEWS,
}


def classify_source(url: str) -> SourceProfile:
    domain = registrable_domain(url)
    source_type = None
    # Most specific match first: "nsearchives.nseindia.com" before "nseindia.com".
    parts = domain.split(".")
    for i in range(len(parts) - 1):
        candidate = ".".join(parts[i:])
        if candidate in DOMAIN_TYPES:
            source_type = DOMAIN_TYPES[candidate]
            break
    if source_type is None and (domain.endswith(".gov.in") or domain.endswith(".nic.in")):
        source_type = SourceType.REGULATOR
    source_type = source_type or SourceType.OTHER
    reliability, label = _TYPE_DEFAULTS[source_type]
    if domain.endswith(".demo.test"):
        label += " (demo data)"
    return SourceProfile(source_type, reliability, label)


# ------------------------------------------------------------------------------------------
# Recency
# ------------------------------------------------------------------------------------------

# Days after which a source counts for half as much, per claim type.
HALF_LIFE_DAYS: dict[ClaimType, int] = {
    ClaimType.CREDENTIAL: 90,  # registrations can be granted or cancelled at any time
    ClaimType.STOCK_CALL: 180,
    ClaimType.OTHER: 365,
    ClaimType.COMPANY_FACT: 730,
    ClaimType.RETURN_PROMISE: 730,  # investor cautions stay valid for years
    ClaimType.PAST_PERFORMANCE: 1095,
    ClaimType.MARKET_FACT: 1825,  # historical facts don't expire
}
UNKNOWN_RECENCY = 0.5


def recency_score(
    published: date | None, claim_type: ClaimType, as_of: date | None = None
) -> float:
    if published is None:
        return UNKNOWN_RECENCY
    today = as_of or date.today()
    age = (today - published).days
    if age < 0:
        return UNKNOWN_RECENCY  # a future date is bad metadata, not a fresh source
    return round(max(0.05, 0.5 ** (age / HALF_LIFE_DAYS[claim_type])), 3)


# ------------------------------------------------------------------------------------------
# Relevance
# ------------------------------------------------------------------------------------------

_STOPWORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "at",
        "for",
        "by",
        "with",
        "from",
        "this",
        "that",
        "these",
        "those",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "it",
        "its",
        "as",
        "will",
        "would",
        "can",
        "could",
        "has",
        "have",
        "had",
        "not",
        "no",
        "but",
        "if",
        "then",
        "than",
        "so",
        "such",
        "into",
        "over",
        "about",
        "after",
        "before",
        "more",
        "most",
        "very",
        "just",
        "also",
        "only",
        "my",
        "your",
        "our",
        "their",
        "his",
        "her",
        "them",
        "they",
        "we",
        "you",
        "i",
        "me",
        "he",
        "she",
        "ki",
        "ka",
        "ke",
        "ko",
        "se",
        "mein",
        "hai",
        "hain",
        "tha",
        "aur",
        "ye",
        "yeh",
        "wo",
        "kya",
        "bhi",
        "toh",
    ]
)
_TOKEN = re.compile(r"[\w%₹]+", re.UNICODE)
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _keywords(text: str) -> set[str]:
    return {
        t
        for t in _TOKEN.findall(normalize_for_match(text))
        if (len(t) >= 3 or t.isdigit()) and t not in _STOPWORDS
    }


def _numbers(text: str) -> set[str]:
    return set(_NUM.findall(text.replace(",", "")))


def relevance_score(claim: Claim, passage: str) -> float:
    keys = _keywords(claim.text) | {t.lower() for t in claim.tickers}
    if not keys or not passage.strip():
        return 0.0
    passage_tokens = set(_TOKEN.findall(normalize_for_match(passage)))
    coverage = len(keys & passage_tokens) / len(keys)
    claim_nums = _numbers(claim.text)
    number_score = (1.0 if claim_nums & _numbers(passage) else 0.0) if claim_nums else coverage
    tickers = {t.lower() for t in claim.tickers}
    if not tickers:
        return round(min(1.0, 0.9 * coverage + 0.1 * number_score), 3)
    ticker_score = 1.0 if tickers & passage_tokens else 0.0
    return round(min(1.0, 0.7 * coverage + 0.2 * ticker_score + 0.1 * number_score), 3)


def best_passages(claim: Claim, text: str, *, k: int = 2, window: int = 2) -> list[str]:
    """The k most relevant, non-overlapping windows of ``window`` sentences, in page order."""
    sentences = split_sentences(text)
    if not sentences:
        return []
    windows = [
        (i, " ".join(sentences[i : i + window])) for i in range(max(1, len(sentences) - window + 1))
    ]
    scored = sorted(windows, key=lambda w: -relevance_score(claim, w[1]))
    chosen: list[tuple[int, str]] = []
    for i, passage in scored:
        if relevance_score(claim, passage) == 0:
            break
        if all(abs(i - j) >= window for j, _ in chosen):
            chosen.append((i, passage))
        if len(chosen) == k:
            break
    return [p for _, p in sorted(chosen)]


# ------------------------------------------------------------------------------------------
# Putting it together
# ------------------------------------------------------------------------------------------


def assess_source(
    url: str,
    published: date | None,
    claim: Claim,
    passage: str,
    *,
    as_of: date | None = None,
) -> tuple[SourceType, SourceQuality]:
    profile = classify_source(url)
    quality = SourceQuality(
        reliability=profile.reliability,
        recency=recency_score(published, claim.claim_type, as_of),
        relevance=relevance_score(claim, passage),
    )
    return profile.source_type, quality


def _band(score: float) -> str:
    return "High" if score >= 0.75 else "Medium" if score >= 0.45 else "Low"


def _age_text(published: date | None, as_of: date) -> str:
    if published is None:
        return "Publication date unknown"
    days = (as_of - published).days
    if days < 0:
        return "Publication date looks wrong"
    if days < 31:
        return "Published in the last month"
    if days < 365:
        return f"Published about {days // 30} month{'s' if days >= 60 else ''} ago"
    years = days // 365
    return f"Published about {years} year{'s' if years > 1 else ''} ago"


def describe_quality(
    url: str, published: date | None, quality: SourceQuality, *, as_of: date | None = None
) -> dict[str, str]:
    """Plain-English labels for the evidence-quality indicators in the UI."""
    today = as_of or date.today()
    profile = classify_source(url)
    return {
        "overall": f"{_band(quality.overall)} quality source",
        "reliability": f"{_band(quality.reliability)}: {profile.label}",
        "recency": f"{_band(quality.recency)}: {_age_text(published, today)}",
        "relevance": f"{_band(quality.relevance)}: "
        + (
            "talks directly about this claim"
            if quality.relevance >= 0.75
            else "partly related to this claim"
            if quality.relevance >= 0.45
            else "only loosely related to this claim"
        ),
    }

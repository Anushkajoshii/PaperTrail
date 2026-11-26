"""Rule-based claim finder.

Two uses:
1. It backs the offline mock LLM, so the full pipeline runs with no keys.
2. It is the honest *baseline* in the eval report: an LLM extractor has to beat simple rules to
   justify its cost.
"""

from __future__ import annotations

import re

from papertrail.models import ClaimType
from papertrail.text import parse_inr_amount, parse_percentages, split_sentences

_HAS_NUMBER = re.compile(r"\d|₹|\blakh|\bcrore|\bcr\b", re.IGNORECASE)

_RULES: list[tuple[ClaimType, re.Pattern[str]]] = [
    (
        ClaimType.CREDENTIAL,
        re.compile(
            r"\b(sebi[- ]?registered|registered (investment )?advis[eo]r|research analyst|"
            r"\bria\b|certified|registration (no|number))",
            re.IGNORECASE,
        ),
    ),
    (
        ClaimType.STOCK_CALL,
        re.compile(
            r"\btarget\b|stop[- ]?loss|\bbuy\b|\bsell\b|kharid|bech|will (reach|hit|touch|go)|"
            r"jayega|jaega|multibagger|खरीद",
            re.IGNORECASE,
        ),
    ),
    (
        ClaimType.RETURN_PROMISE,
        re.compile(
            r"guarantee|assured|pakka|sure[- ]?shot|fixed return|every month|per month|monthly|"
            r"har mahine|risk[- ]?free|double your|paisa double|no loss|gaaranti|गारंटी|पक्का",
            re.IGNORECASE,
        ),
    ),
    (
        ClaimType.MARKET_FACT,
        re.compile(r"\bnifty\b|\bsensex\b|bank nifty|all[- ]?time high|\bindex\b", re.IGNORECASE),
    ),
    (
        ClaimType.PAST_PERFORMANCE,
        re.compile(
            r"\bgave\b|returned|\bdiya\b|\bgrew\b|\brose\b|\bfell\b|\bup \d|\bin (19|20)\d\d\b|"
            r"last year|pichle|\bmade\b|\bearned\b|kamaya|दिया",
            re.IGNORECASE,
        ),
    ),
    (
        ClaimType.COMPANY_FACT,
        re.compile(r"revenue|profit|earnings|quarter|\bfy ?\d\d|results|order book", re.IGNORECASE),
    ),
]

_WHY = {
    ClaimType.CREDENTIAL: "SEBI's public registry can show whether this registration exists.",
    ClaimType.RETURN_PROMISE: "Compare the promised return with how market investments behave.",
    ClaimType.STOCK_CALL: "Actual share prices over the stated period can show if it came true.",
    ClaimType.MARKET_FACT: "Exchange records show index levels and dates.",
    ClaimType.PAST_PERFORMANCE: "Historical prices or reports can confirm the stated performance.",
    ClaimType.COMPANY_FACT: "Company filings and results can confirm these figures.",
    ClaimType.OTHER: "It states a specific number that public records may confirm.",
}

# Upper-case words that look like tickers but are not.
_NOT_TICKERS = frozenset(
    [
        "SEBI",
        "NSE",
        "BSE",
        "RBI",
        "IPO",
        "ETF",
        "SIP",
        "NIFTY",
        "SENSEX",
        "VIP",
        "FD",
        "GDP",
        "EMI",
        "CEO",
        "CFO",
        "USA",
        "INR",
        "RS",
        "MF",
        "NAV",
        "CAGR",
        "ROI",
        "PE",
        "EPS",
        "ATH",
        "FY",
        "AMC",
        "NFO",
        "KYC",
        "UPI",
        "GST",
        "LTCG",
        "STCG",
        "ITR",
        "PAN",
        "OTP",
        "RA",
        "RIA",
        "AI",
        "YOU",
        "THE",
        "AND",
        "FOR",
        "NOT",
        "BUY",
        "SELL",
        "TARGET",
        "STOP",
        "LOSS",
        "JOIN",
        "LINK",
        "TELEGRAM",
        "WHATSAPP",
        "NOW",
        "FREE",
    ]
)
_TICKER = re.compile(r"\b[A-Z][A-Z0-9&]{2,14}\b")


def classify_sentence(sentence: str) -> ClaimType | None:
    """Return the claim type for a sentence, or None if it isn't a checkable claim."""
    if len(sentence) < 12 or sentence.rstrip().endswith("?"):
        return None
    for claim_type, pattern in _RULES:
        if pattern.search(sentence):
            # Credentials and promises are checkable even without numbers; others need one.
            if claim_type in {ClaimType.CREDENTIAL, ClaimType.RETURN_PROMISE}:
                return claim_type
            if _HAS_NUMBER.search(sentence):
                return claim_type
    if parse_percentages(sentence) or parse_inr_amount(sentence) is not None:
        return ClaimType.OTHER
    return None


def find_tickers(sentence: str) -> list[str]:
    seen: list[str] = []
    for t in _TICKER.findall(sentence):
        if t not in _NOT_TICKERS and t not in seen:
            seen.append(t)
    return seen


def heuristic_claims(text: str) -> list[dict]:
    """Claims as plain dicts in the same shape the LLM is asked to return."""
    out = []
    for sentence in split_sentences(text):
        claim_type = classify_sentence(sentence)
        if claim_type is None:
            continue
        out.append(
            {
                "text": sentence,
                "quote": sentence,
                "claim_type": claim_type.value,
                "tickers": find_tickers(sentence),
                "why_checkable": _WHY[claim_type],
            }
        )
    return out

"""Turn a stock-call claim into something that can be settled: symbol, target and deadline.

Deterministic on purpose: the numbers that decide "hit" or "missed" must come from the
creator's own words, never from an AI guess. Works on English, Hindi-in-Latin (Hinglish) and
common Devanagari month names.

    "TATAMOTORS ka target ₹1500 hai, March tak pakka jayega"  -> up to ₹1500 by 31 March
    "Buy ORIONBANK with a target of ₹950 and stop loss ₹780"  -> up to ₹950 (stop loss ignored)
    "Lotus Foods is saal 50% dega"                            -> up 50% by 31 December
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

from papertrail.ledger.models import Direction
from papertrail.models import Claim, ClaimType
from papertrail.text.numbers import _AMOUNT, _MULTIPLIERS

DEFAULT_HORIZON_DAYS = 90

_MONTHS = {
    **{m.lower(): i for i, m in enumerate(calendar.month_name) if m},
    **{m.lower(): i for i, m in enumerate(calendar.month_abbr) if m},
    "sept": 9,
    # Devanagari spellings creators use
    "जनवरी": 1,
    "फरवरी": 2,
    "मार्च": 3,
    "अप्रैल": 4,
    "मई": 5,
    "जून": 6,
    "जुलाई": 7,
    "अगस्त": 8,
    "सितंबर": 9,
    "अक्टूबर": 10,
    "नवंबर": 11,
    "दिसंबर": 12,
}
_MONTH_RE = re.compile(
    r"(?<![\w])(" + "|".join(sorted(map(re.escape, _MONTHS), key=len, reverse=True)) + r")"
    r"(?:\s*['\u2019]?\s*(\d{4}|\d{2}))?(?![\w])",
    re.IGNORECASE,
)
_RELATIVE = re.compile(
    r"(\d+)\s*(months?|mahine|mahino|mahinon|महीने|weeks?|hafte|haftey|हफ्ते|days?|din|दिन)",
    re.IGNORECASE,
)
_THIS_YEAR = re.compile(r"\b(this year|is saal|iss saal|year[- ]end|saal ke end)\b|इस साल", re.I)
_NEXT_YEAR = re.compile(r"\b(next year|agle saal)\b|अगले साल", re.IGNORECASE)
_TARGET_CUE = re.compile(
    r"target|reach|hit|touch|jayega|jaayega|jaega|pahunche|pahunchega|tak\b|cross|to\b|पहुंच|टारगेट",
    re.IGNORECASE,
)
_STOP_LOSS = re.compile(r"(stop\s*-?\s*loss|\bsl\b|स्टॉप)\s*(of|at|:)?\s*$", re.IGNORECASE)
_DOWN = re.compile(
    r"\b(fall|drop|crash|decline|slide|sell|short|girega|girne|neeche|niche|tootega)\b|गिर",
    re.IGNORECASE,
)
_FUNDAMENTALS = re.compile(
    r"\b(profit|revenue|sales|earnings|eps|margin|ebitda|dividend|munafa|order book)\b|मुनाफ",
    re.IGNORECASE,
)
_PERCENT_MOVE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:%|percent|pratishat)\s*(?:returns?|upar|up|gain|dega|degi|badhega|"
    r"jump|rise|tak|neeche|down|girega)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Prediction:
    ticker: str
    direction: Direction
    target_price: float | None
    target_pct: float | None
    due_on: date
    deadline_stated: bool


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def parse_deadline(text: str, made_on: date) -> tuple[date, bool]:
    """Return (deadline, stated). Without a stated deadline, a default horizon is used."""
    m = _MONTH_RE.search(text)
    if m:
        month = _MONTHS[m.group(1).lower()]
        year_txt = m.group(2)
        if year_txt:
            year = int(year_txt) + (2000 if len(year_txt) == 2 else 0)
        else:  # "March tak": the next March end that has not passed yet
            year = made_on.year if month >= made_on.month else made_on.year + 1
        return _month_end(year, month), True
    m = _RELATIVE.search(text)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        if unit.startswith(("month", "mahin", "महीने")):
            month0 = made_on.month - 1 + n
            year, month = made_on.year + month0 // 12, month0 % 12 + 1
            day = min(made_on.day, calendar.monthrange(year, month)[1])
            return date(year, month, day), True
        days = n * 7 if unit.startswith(("week", "haft", "हफ्ते")) else n
        return made_on + timedelta(days=days), True
    if _NEXT_YEAR.search(text):
        return date(made_on.year + 1, 12, 31), True
    if _THIS_YEAR.search(text):
        return date(made_on.year, 12, 31), True
    return made_on + timedelta(days=DEFAULT_HORIZON_DAYS), False


def parse_target_price(text: str) -> float | None:
    """The rupee target: the amount after a cue like 'target' or 'tak', never the stop loss."""
    candidates: list[tuple[int, int, float]] = []  # (no cue nearby, position, value)
    for m in _AMOUNT.finditer(text):
        raw = m.group(0).strip()
        unit = (m.group("unit") or "").lower()
        if not unit and raw[:1] not in "₹rRiI":
            continue  # a bare number (a year, a percentage) is not a price
        if text[m.end() : m.end() + 1] == "%":
            continue
        if _STOP_LOSS.search(text[max(0, m.start() - 20) : m.start()]):
            continue
        value = float(m.group("num").replace(",", "")) * _MULTIPLIERS.get(unit, 1)
        window = text[max(0, m.start() - 25) : m.end() + 25]
        candidates.append((0 if _TARGET_CUE.search(window) else 1, m.start(), value))
    return min(candidates)[2] if candidates else None


def parse_target_pct(text: str) -> float | None:
    m = _PERCENT_MOVE.search(text)
    return float(m.group(1)) if m else None


def parse_prediction(claim: Claim, made_on: date) -> Prediction | None:
    """A trackable prediction, or None if the claim has no symbol or no target."""
    if claim.claim_type is not ClaimType.STOCK_CALL or not claim.tickers:
        return None
    text = f"{claim.quote} | {claim.text}"
    price = parse_target_price(claim.quote) or parse_target_price(claim.text)
    pct = None if price else (parse_target_pct(claim.quote) or parse_target_pct(claim.text))
    if price is None and pct is None:
        return None
    if pct is not None and _FUNDAMENTALS.search(text):
        return None  # "profit will jump 50%" is about the business, not the share price
    due_on, stated = parse_deadline(text, made_on)
    return Prediction(
        ticker=claim.tickers[0].upper(),
        direction=Direction.DOWN if _DOWN.search(text) else Direction.UP,
        target_price=price,
        target_pct=pct,
        due_on=due_on,
        deadline_stated=stated,
    )

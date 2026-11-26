"""Parse money amounts and percentages the way Indian finance creators say them.

Examples: "₹2.5 lakh" -> 250000, "Rs 5 crore" -> 50000000, "50k" -> 50000, "1,00,000" -> 100000,
"300%" -> 300.0, "5 percent" -> 5.0, "do guna" (double) is out of scope (the LLM handles words).
"""

from __future__ import annotations

import re

_MULTIPLIERS = {
    "k": 1_000,
    "thousand": 1_000,
    "hazaar": 1_000,
    "hazar": 1_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "lac": 100_000,
    "lacs": 100_000,
    "l": 100_000,
    "cr": 10_000_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
    "mn": 1_000_000,
    "million": 1_000_000,
    "bn": 1_000_000_000,
    "billion": 1_000_000_000,
}

_AMOUNT = re.compile(
    r"(?:₹|rs\.?|inr)?\s*"
    r"(?P<num>\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"\s*(?P<unit>k|thousand|hazaa?r|lakhs?|lacs?|l|cr|crores?|mn|million|bn|billion)?\b",
    re.IGNORECASE,
)
_CURRENCY_HINT = re.compile(r"₹|\brs\b|\brs\.|\binr\b|rupees?", re.IGNORECASE)
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b|per\s*cent\b|pratishat\b)", re.IGNORECASE)


def parse_inr_amount(text: str) -> float | None:
    """Return the first rupee amount in ``text``, or None.

    A bare number counts only if it has a unit (lakh, crore, k...) or a currency marker, so
    "in 2023" is not mistaken for ₹2023.
    """
    has_currency = bool(_CURRENCY_HINT.search(text))
    for m in _AMOUNT.finditer(text):
        unit = (m.group("unit") or "").lower()
        if not unit and not has_currency:
            continue
        if not unit and m.group(0).strip()[:1] not in "₹rRiI":
            # Currency mentioned somewhere, but this particular number isn't marked as money.
            continue
        value = float(m.group("num").replace(",", ""))
        return value * _MULTIPLIERS.get(unit, 1)
    return None


def parse_percentages(text: str) -> list[float]:
    return [float(x) for x in _PERCENT.findall(text)]

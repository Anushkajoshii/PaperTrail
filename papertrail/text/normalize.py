"""Sentence splitting and normalisation for matching quotes against source text."""

from __future__ import annotations

import re
import unicodedata

# Sentence ends: ! ? and the Devanagari danda (।), or a full stop followed by a space and a capital
# letter / Devanagari. Decimals ("2.5") have no space so stay intact; common abbreviations
# ("Rs. 500", "No. 3") are protected explicitly.
_SENTENCE_END = re.compile(
    r"(?<=[!?।])\s+"
    r"|(?<!\bRs\.)(?<!\brs\.)(?<!\bNo\.)(?<!\bno\.)(?<!\bMr\.)(?<!\bDr\.)(?<!\bvs\.)"
    r"(?<=\.)\s+(?=[A-Z\u0900-\u097F\"'“(])"
    r"|\n+"
)
_NON_WORD = re.compile(r"[^\w\s%₹]", re.UNICODE)
_SPACES = re.compile(r"\s+")
_CURRENCY_WORD = re.compile(r"\b(?:rs\.?|inr|rupees?)(?=\s*\d|\s|$)")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s and s.strip()]


def normalize_for_match(text: str) -> str:
    """Lowercase, unify unicode forms and quotes, drop punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = _CURRENCY_WORD.sub("₹ ", text)
    text = _NON_WORD.sub(" ", text)
    return _SPACES.sub(" ", text).strip()

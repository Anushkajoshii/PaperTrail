"""Sentence splitting and normalisation for matching quotes against source text."""

from __future__ import annotations

import re
import unicodedata

# Sentence ends: . ! ? and the Devanagari danda (।). Keeps decimals like 2.5 intact.
_SENTENCE_END = re.compile(r"(?<=[!?।])\s+|(?<=[^\d\s]\.)\s+|\n+")
_NON_WORD = re.compile(r"[^\w\s%₹]", re.UNICODE)
_SPACES = re.compile(r"\s+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s and s.strip()]


def normalize_for_match(text: str) -> str:
    """Lowercase, unify unicode forms and quotes, drop punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("rs.", "₹").replace("rs ", "₹ ").replace("inr", "₹")
    text = _NON_WORD.sub(" ", text)
    return _SPACES.sub(" ", text).strip()

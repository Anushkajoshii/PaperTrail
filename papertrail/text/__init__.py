"""Text utilities for Indian finance content: language, sentences, numbers and amounts."""

from papertrail.text.language import detect_language
from papertrail.text.normalize import normalize_for_match, split_sentences
from papertrail.text.numbers import parse_inr_amount, parse_percentages

__all__ = [
    "detect_language",
    "normalize_for_match",
    "parse_inr_amount",
    "parse_percentages",
    "split_sentences",
]

"""Detect English, Hindi (Devanagari) or Hinglish (romanised Hindi mixed with English).

A light heuristic is enough here. It picks the transcription language and tells the prompts what to
expect, and the LLM handles the actual understanding. It is fast, offline and easy to test.
"""

from __future__ import annotations

import re

from papertrail.models import Language

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")
_WORD = re.compile(r"[A-Za-z]+")

# Common romanised Hindi words that rarely appear in English finance talk.
HINGLISH_MARKERS = frozenset(
    {
        "hai",
        "hain",
        "tha",
        "thi",
        "the",
        "ho",
        "hoga",
        "hogi",
        "hoge",
        "raha",
        "rahi",
        "rahe",
        "kar",
        "karo",
        "karna",
        "karke",
        "kiya",
        "kiye",
        "nahi",
        "nahin",
        "mat",
        "aur",
        "ya",
        "ki",
        "ka",
        "ke",
        "ko",
        "se",
        "mein",
        "mai",
        "main",
        "mera",
        "meri",
        "mere",
        "tera",
        "teri",
        "tum",
        "aap",
        "apna",
        "apni",
        "apne",
        "hum",
        "humne",
        "yeh",
        "ye",
        "woh",
        "wo",
        "kya",
        "kyun",
        "kyunki",
        "kaise",
        "kab",
        "jab",
        "tab",
        "agar",
        "toh",
        "to",
        "bhai",
        "bhaiyon",
        "dosto",
        "doston",
        "paisa",
        "paise",
        "lakh",
        "crore",
        "wala",
        "wali",
        "wale",
        "sab",
        "bahut",
        "zyada",
        "kam",
        "milega",
        "milegi",
        "dega",
        "degi",
        "denge",
        "lena",
        "lo",
        "dekho",
        "suno",
        "abhi",
        "pakka",
        "sirf",
        "bas",
        "jaldi",
        "baad",
        "pehle",
    }
)
# Words above that are also ordinary English and should not count on their own.
_AMBIGUOUS = frozenset({"to", "the", "main", "ho", "ye", "kam", "bas", "lo", "mat", "ya"})


def detect_language(text: str) -> Language:
    """Classify text as English, Hindi or Hinglish. Empty or unclear text defaults to English."""
    letters_dev = len(_DEVANAGARI.findall(text))
    letters_lat = len(_LATIN.findall(text))
    total = letters_dev + letters_lat
    if total == 0:
        return Language.ENGLISH

    dev_share = letters_dev / total
    if dev_share >= 0.6:
        return Language.HINDI
    if dev_share >= 0.15:
        return Language.HINGLISH  # Devanagari mixed with substantial English

    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return Language.ENGLISH
    markers = sum(1 for w in words if w in HINGLISH_MARKERS and w not in _AMBIGUOUS)
    if markers >= 2 and markers / len(words) >= 0.12:
        return Language.HINGLISH
    return Language.ENGLISH

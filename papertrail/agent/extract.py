"""Claim extraction: transcript in, a list of checkable, *grounded* claims out.

Steps:
1. Detect the language (English / Hindi / Hinglish).
2. Split long transcripts into overlapping chunks so nothing is cut mid-sentence.
3. Ask the LLM for claims as structured output (``ClaimExtractionOutput``).
4. Ground every claim: its quote must actually appear in the transcript. Claims the model
   invented are dropped and recorded, never shown to users.
5. Clean up: normalise tickers, remove duplicates, cap the count, attach timestamps.

Run it on a file:  uv run python -m papertrail.agent.extract examples/hinglish_reel.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator
from rapidfuzz import fuzz

from papertrail.agent.heuristics import heuristic_claims
from papertrail.agent.prompts import (
    EXTRACT_PROMPT_VERSION,
    EXTRACT_SYSTEM,
    EXTRACT_USER,
    escape_data,
    unescape_data,
)
from papertrail.config import get_settings
from papertrail.llm import (
    LLMRequest,
    Provider,
    Purpose,
    UsageLog,
    generate_structured,
    get_provider,
    register_mock_handler,
)
from papertrail.models import Claim, ClaimType, Language, TranscriptSegment
from papertrail.text import detect_language, normalize_for_match, split_sentences

# ------------------------------------------------------------------------------------------
# What the LLM returns. Deliberately lenient: unknown claim types become "other", extra keys are
# ignored, and tickers are cleaned. Strict rules apply later, when we build Claim objects.
# ------------------------------------------------------------------------------------------


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    text: str = Field(description="The claim as one clear, self-contained English sentence.")
    quote: str = Field(description="The speaker's exact words, copied verbatim.")
    claim_type: ClaimType
    tickers: list[str] = Field(default_factory=list)
    why_checkable: str = ""

    @field_validator("claim_type", mode="before")
    @classmethod
    def _lenient_type(cls, v: object) -> object:
        if isinstance(v, str):
            key = v.strip().lower().replace(" ", "_").replace("-", "_")
            return key if key in ClaimType._value2member_map_ else ClaimType.OTHER.value
        return v

    @field_validator("tickers", mode="before")
    @classmethod
    def _clean_tickers(cls, v: object) -> object:
        if v is None:
            return []
        if isinstance(v, str):
            v = [v]
        return [t for t in (normalize_ticker(x) for x in v if isinstance(x, str)) if t]


class ClaimExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claims: list[ExtractedClaim] = Field(default_factory=list)


_TICKER_OK = re.compile(r"^[A-Z0-9&\-]{1,20}$")


def normalize_ticker(raw: str) -> str | None:
    t = raw.strip().upper().removeprefix("NSE:").removeprefix("BSE:")
    for suffix in (".NS", ".BO", "-EQ"):
        t = t.removesuffix(suffix)
    return t if _TICKER_OK.match(t) else None


# ------------------------------------------------------------------------------------------
# Result
# ------------------------------------------------------------------------------------------


@dataclass
class DroppedClaim:
    claim: ExtractedClaim
    reason: str


@dataclass
class ExtractionResult:
    claims: list[Claim]
    language: Language
    prompt_version: str = EXTRACT_PROMPT_VERSION
    chunks: int = 1
    dropped: list[DroppedClaim] = field(default_factory=list)
    usage: UsageLog = field(default_factory=UsageLog)


# ------------------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------------------

GROUNDING_THRESHOLD = 90  # rapidfuzz partial_ratio, 0-100
DUPLICATE_THRESHOLD = 90  # rapidfuzz token_set_ratio between claim texts


def chunk_transcript(text: str, max_chars: int = 6000, overlap_sentences: int = 2) -> list[str]:
    """Split into chunks of whole sentences, overlapping a little so claims aren't cut in half."""
    sentences = split_sentences(text)
    if not sentences:
        return []
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for sentence in sentences:
        if current and size + len(sentence) > max_chars:
            chunks.append(" ".join(current))
            current = current[-overlap_sentences:] if overlap_sentences else []
            size = sum(len(s) + 1 for s in current)
        current.append(sentence)
        size += len(sentence) + 1
    chunks.append(" ".join(current))
    return chunks


def is_grounded(quote: str, normalized_source: str) -> bool:
    """True if the quote really appears in the source, allowing tiny transcription differences."""
    q = normalize_for_match(quote)
    if len(q) < 4:
        return False
    if q in normalized_source:
        return True
    return len(q) >= 12 and fuzz.partial_ratio(q, normalized_source) >= GROUNDING_THRESHOLD


def find_timestamp(quote: str, segments: list[TranscriptSegment]) -> float | None:
    """Start time of the segment where the quote begins (quotes can span several segments)."""
    if not segments:
        return None
    q = normalize_for_match(quote)
    starts: list[tuple[int, float]] = []  # (char offset in joined text, segment start time)
    parts: list[str] = []
    offset = 0
    for seg in segments:
        text = normalize_for_match(seg.text)
        starts.append((offset, seg.start_seconds))
        parts.append(text)
        offset += len(text) + 1
    joined = " ".join(parts)
    pos = joined.find(q)
    if pos < 0:
        alignment = fuzz.partial_ratio_alignment(q, joined)
        if alignment is None or alignment.score < GROUNDING_THRESHOLD:
            return None
        pos = alignment.dest_start
    return next(t for off, t in reversed(starts) if off <= pos)


_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _is_duplicate(candidate: ExtractedClaim, kept: list[ExtractedClaim]) -> bool:
    """Near-identical wording AND the same numbers. "Nifty at 24,000" != "Nifty at 24,100"."""
    c = normalize_for_match(candidate.text)
    c_nums = sorted(_NUMBER.findall(candidate.text))
    return any(
        sorted(_NUMBER.findall(k.text)) == c_nums
        and fuzz.token_set_ratio(c, normalize_for_match(k.text)) >= DUPLICATE_THRESHOLD
        for k in kept
    )


# Type priority when trimming to max_claims: what matters most to an ordinary investor first.
_PRIORITY = {
    ClaimType.RETURN_PROMISE: 0,
    ClaimType.CREDENTIAL: 1,
    ClaimType.PAST_PERFORMANCE: 2,
    ClaimType.STOCK_CALL: 3,
    ClaimType.COMPANY_FACT: 4,
    ClaimType.MARKET_FACT: 5,
    ClaimType.OTHER: 6,
}


# ------------------------------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------------------------------


def extract_claims(
    transcript: str,
    *,
    provider: Provider | None = None,
    segments: list[TranscriptSegment] | None = None,
    language_hint: Language | None = None,
    max_claims: int | None = None,
    max_chunk_chars: int = 6000,
) -> ExtractionResult:
    settings = get_settings()
    provider = provider or get_provider(settings)
    max_claims = max_claims or settings.max_claims_per_check
    language = language_hint or detect_language(transcript)
    chunks = chunk_transcript(transcript, max_chars=max_chunk_chars)
    result = ExtractionResult(claims=[], language=language, chunks=len(chunks))
    if not chunks:
        return result

    normalized_source = normalize_for_match(transcript)
    kept: list[ExtractedClaim] = []
    for chunk in chunks:
        request = LLMRequest(
            system=EXTRACT_SYSTEM.format(max_claims=max_claims),
            user=EXTRACT_USER.format(language=language.value, transcript=escape_data(chunk)),
            output_model=ClaimExtractionOutput,
            purpose=Purpose.EXTRACT,
        )
        output = generate_structured(provider, request, usage_log=result.usage).output
        for candidate in output.claims:
            if not is_grounded(candidate.quote, normalized_source):
                result.dropped.append(DroppedClaim(candidate, "quote not found in transcript"))
            elif _is_duplicate(candidate, kept):
                result.dropped.append(DroppedClaim(candidate, "duplicate"))
            else:
                kept.append(candidate)

    if len(kept) > max_claims:
        ranked = sorted(enumerate(kept), key=lambda ic: (_PRIORITY[ic[1].claim_type], ic[0]))
        keep_idx = sorted(i for i, _ in ranked[:max_claims])
        for i, c in enumerate(kept):
            if i not in keep_idx:
                result.dropped.append(DroppedClaim(c, f"over the {max_claims}-claim limit"))
        kept = [kept[i] for i in keep_idx]

    result.claims = [
        Claim(
            text=c.text,
            quote=c.quote,
            claim_type=c.claim_type,
            language=detect_language(c.quote),
            tickers=c.tickers,
            why_checkable=c.why_checkable or None,
            timestamp_seconds=find_timestamp(c.quote, segments or []),
        )
        for c in kept
    ]
    return result


# ------------------------------------------------------------------------------------------
# Offline mock: rule-based extraction so the pipeline works without an LLM.
# ------------------------------------------------------------------------------------------

_TRANSCRIPT_TAG = re.compile(r"<transcript>\n(.*)\n</transcript>", re.DOTALL)


@register_mock_handler(ClaimExtractionOutput)
def _mock_extract(request: LLMRequest) -> ClaimExtractionOutput:
    match = _TRANSCRIPT_TAG.search(request.user)
    text = unescape_data(match.group(1)) if match else ""
    return ClaimExtractionOutput.model_validate({"claims": heuristic_claims(text)})


# ------------------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract checkable claims from a transcript.")
    parser.add_argument("path", help="Text file, or '-' for stdin")
    args = parser.parse_args(argv)
    text = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
    result = extract_claims(text)
    print(
        json.dumps(
            {
                "language": result.language,
                "prompt_version": result.prompt_version,
                "claims": [c.model_dump(mode="json", exclude_none=True) for c in result.claims],
                "dropped": [{"quote": d.claim.quote, "reason": d.reason} for d in result.dropped],
                "cost_usd": result.usage.total_cost_usd,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

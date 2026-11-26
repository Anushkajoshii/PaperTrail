"""Parsing of raw LLM extraction output: lenient on cosmetic issues, strict on substance."""

import itertools
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from papertrail.agent.extract import (
    ClaimExtractionOutput,
    chunk_transcript,
    is_grounded,
    normalize_ticker,
)
from papertrail.agent.heuristics import classify_sentence, find_tickers
from papertrail.models import ClaimType
from papertrail.text import normalize_for_match

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "llm_extraction_outputs.json").read_text()
)


def parse(name: str) -> ClaimExtractionOutput:
    return ClaimExtractionOutput.model_validate(FIXTURES[name])


def test_clean_output():
    out = parse("clean")
    assert out.claims[0].claim_type is ClaimType.STOCK_CALL
    assert out.claims[0].tickers == ["TATAMOTORS"]


def test_messy_claim_types_are_normalised_or_fall_back_to_other():
    types = [c.claim_type for c in parse("messy_types_and_tickers").claims]
    assert types == [
        ClaimType.STOCK_CALL,
        ClaimType.RETURN_PROMISE,
        ClaimType.OTHER,
        ClaimType.PAST_PERFORMANCE,
    ]


def test_messy_tickers_are_cleaned():
    claims = parse("messy_types_and_tickers").claims
    assert claims[0].tickers == ["TATAMOTORS"]
    assert claims[1].tickers == ["RELIANCE", "INFY"]
    assert claims[2].tickers == []


def test_extra_keys_are_ignored():
    assert parse("extra_top_level_keys").claims == []


@pytest.mark.parametrize("name", ["missing_quote", "claims_not_a_list"])
def test_substantive_problems_are_rejected(name):
    # These fail validation, so generate_structured sends feedback and retries.
    with pytest.raises(ValidationError):
        parse(name)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("reliance", "RELIANCE"),
        ("INFY.NS", "INFY"),
        ("BSE:TCS", "TCS"),
        ("SBIN-EQ", "SBIN"),
        ("M&M", "M&M"),
        ("BAJAJ-AUTO", "BAJAJ-AUTO"),
        ("two words", None),
        ("", None),
    ],
)
def test_normalize_ticker(raw, expected):
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize(
    ("quote", "grounded"),
    [
        ("TATAMOTORS ka target ₹1500 hai", True),
        ("tatamotors KA target ₹1500 hai!!", True),  # case and punctuation differ
        ("TATAMOTORS ka target Rs 1500 hai", True),  # Rs vs ₹
        ("TATAMOTORS ka target ₹2500 hai", False),  # a different number is a different claim
        ("RELIANCE will double", False),
        ("ka", False),  # too short to mean anything
    ],
)
def test_grounding(quote, grounded):
    source = normalize_for_match("Doston, TATAMOTORS ka target ₹1500 hai, March tak.")
    assert is_grounded(quote, source) is grounded


def test_chunking_keeps_whole_sentences_with_overlap():
    text = " ".join(f"Sentence number {i} is here." for i in range(20))
    chunks = chunk_transcript(text, max_chars=120, overlap_sentences=1)
    assert len(chunks) > 1
    for a, b in itertools.pairwise(chunks):
        assert a.split(". ")[-1].rstrip(".") in b  # last sentence repeats at start of next
    assert all(c.endswith(".") for c in chunks)


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("Main SEBI registered advisor hoon", ClaimType.CREDENTIAL),
        ("Guaranteed returns every month, no loss", ClaimType.RETURN_PROMISE),
        ("INFY target 2000 by Diwali", ClaimType.STOCK_CALL),
        ("Sensex crossed 80000 in July 2024", ClaimType.MARKET_FACT),
        ("Is stock ne 2023 mein 150% diya", ClaimType.PAST_PERFORMANCE),
        ("Q2 FY25 revenue grew to 5000 crore", ClaimType.COMPANY_FACT),
        ("I think this sector looks good", None),
        ("Will the market fall 10% tomorrow?", None),
        ("Hi", None),
    ],
)
def test_heuristic_classification(sentence, expected):
    assert classify_sentence(sentence) == expected


def test_find_tickers_skips_common_acronyms():
    assert find_tickers("Buy HDFCBANK and INFY now, SEBI and NSE data agree, join TELEGRAM") == [
        "HDFCBANK",
        "INFY",
    ]

import pytest

from papertrail.models import Language
from papertrail.text import (
    detect_language,
    normalize_for_match,
    parse_inr_amount,
    parse_percentages,
    split_sentences,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("This stock gave 300% returns in one year. Buy before Monday.", Language.ENGLISH),
        ("Bhai yeh stock pakka 300% dega, abhi kharid lo warna pachtaoge", Language.HINGLISH),
        (
            "Doston, is stock ne ek saal mein 300% return diya hai aur aage bhi milega",
            Language.HINGLISH,
        ),
        ("यह शेयर एक साल में तीन गुना हो जाएगा, अभी खरीदें", Language.HINDI),
        ("यह stock guaranteed 20% monthly return देगा, SEBI registered नहीं हूँ", Language.HINGLISH),
        ("", Language.ENGLISH),
        ("12345 %%% !!!", Language.ENGLISH),
        # A single ambiguous word must not flip English text to Hinglish.
        ("The main reason to buy is the price to earnings ratio.", Language.ENGLISH),
    ],
)
def test_detect_language(text, expected):
    assert detect_language(text) is expected


def test_split_sentences_handles_danda_newlines_and_decimals():
    text = "Nifty is at 24,500.5 today. यह शेयर बढ़ेगा। Buy now!\nTarget ₹2.5 lakh"
    assert split_sentences(text) == [
        "Nifty is at 24,500.5 today.",
        "यह शेयर बढ़ेगा।",
        "Buy now!",
        "Target ₹2.5 lakh",
    ]


def test_normalize_for_match():
    assert normalize_for_match("  Rs. 5 Lakh  “guaranteed”!! ") == "₹ 5 lakh guaranteed"
    assert normalize_for_match("\uff21\uff22\uff23") == "abc"  # full-width letters (NFKC)


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("₹2.5 lakh in 6 months", 250_000),
        ("Rs 5 crore portfolio", 50_000_000),
        ("I made 50k last week", 50_000),
        ("₹1,00,000 invested", 100_000),
        ("INR 300", 300),
        ("2 cr ka profit", 20_000_000),
        ("in 2023 the stock rose", None),
        ("returns of 20 percent", None),
    ],
)
def test_parse_inr_amount(text, amount):
    assert parse_inr_amount(text) == amount


def test_parse_percentages():
    assert parse_percentages("gave 300% and then 12.5 percent, 5 pratishat") == [300, 12.5, 5]
    assert parse_percentages("no numbers here") == []

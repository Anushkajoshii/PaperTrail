from datetime import date

import pytest

from papertrail.models import Claim, ClaimType, SourceQuality, SourceType
from papertrail.tools.source_quality import (
    UNKNOWN_RECENCY,
    assess_source,
    best_passages,
    classify_source,
    describe_quality,
    recency_score,
    relevance_score,
)

TODAY = date(2026, 11, 26)


def claim(text, claim_type=ClaimType.PAST_PERFORMANCE, tickers=()):
    return Claim(text=text, quote=text, claim_type=claim_type, tickers=list(tickers))


@pytest.mark.parametrize(
    ("url", "source_type"),
    [
        ("https://www.sebi.gov.in/enforcement/orders.html", SourceType.REGULATOR),
        ("https://www.nseindia.com/get-quotes/equity?symbol=INFY", SourceType.EXCHANGE),
        ("https://nsearchives.nseindia.com/corporate/x.pdf", SourceType.COMPANY_FILING),
        ("https://economictimes.indiatimes.com/markets/x", SourceType.REPUTABLE_NEWS),
        ("https://someone.substack.com/p/tips", SourceType.BLOG),
        ("https://m.youtube.com/watch?v=1", SourceType.SOCIAL),
        ("https://www.india.gov.in/topics/finance", SourceType.REGULATOR),
        ("https://random-stock-tips.xyz/post", SourceType.OTHER),
        ("https://exchange.demo.test/quotes/X", SourceType.EXCHANGE),
    ],
)
def test_classify_source(url, source_type):
    assert classify_source(url).source_type is source_type


def test_reliability_ordering_and_demo_label():
    order = [
        classify_source(u).reliability
        for u in (
            "https://sebi.gov.in",
            "https://nseindia.com",
            "https://livemint.com",
            "https://x.blogspot.com",
            "https://instagram.com",
        )
    ]
    assert order == sorted(order, reverse=True)
    assert classify_source("https://news.demo.test/a").label.endswith("(demo data)")


def test_recency_depends_on_claim_type():
    two_years_ago = date(2024, 11, 26)
    cred = recency_score(two_years_ago, ClaimType.CREDENTIAL, TODAY)
    fact = recency_score(two_years_ago, ClaimType.MARKET_FACT, TODAY)
    assert cred < 0.1 < 0.7 < fact
    assert recency_score(TODAY, ClaimType.STOCK_CALL, TODAY) == 1.0
    assert recency_score(None, ClaimType.OTHER, TODAY) == UNKNOWN_RECENCY
    assert recency_score(date(2030, 1, 1), ClaimType.OTHER, TODAY) == UNKNOWN_RECENCY
    assert recency_score(date(1990, 1, 1), ClaimType.STOCK_CALL, TODAY) == 0.05  # floor


def test_relevance_scores_direct_passages_highest():
    c = claim("TATAMOTORS gave 300% returns in 2023.", tickers=["TATAMOTORS"])
    direct = relevance_score(c, "In 2023 TATAMOTORS shares gave returns of about 100%, not 300%.")
    partial = relevance_score(c, "Auto stocks gave strong returns in 2023.")
    unrelated = relevance_score(c, "The monsoon arrived early in Kerala this year.")
    assert direct > 0.75 > partial > unrelated
    assert relevance_score(c, "") == 0.0


def test_best_passages_picks_relevant_non_overlapping_windows():
    text = (
        "Markets opened flat. TATAMOTORS rose 4% today. Volumes were high. "
        "The weather was pleasant. Analysts expect TATAMOTORS earnings in May. Lunch was nice."
    )
    c = claim("TATAMOTORS rose 4% today.", ClaimType.MARKET_FACT, ["TATAMOTORS"])
    passages = best_passages(c, text, k=2, window=2)
    assert len(passages) == 2
    assert "TATAMOTORS rose 4% today." in passages[0]
    assert best_passages(c, "Nothing related here at all.") == []


def test_assess_source_and_plain_language_labels():
    c = claim(
        "Nifty 50 hit an all-time high of 26,277 on 27 September 2024.", ClaimType.MARKET_FACT
    )
    source_type, q = assess_source(
        "https://www.nseindia.com/indices",
        date(2024, 9, 30),
        c,
        "The Nifty 50 hit an all-time high of 26,277 on 27 September 2024.",
        as_of=TODAY,
    )
    assert source_type is SourceType.EXCHANGE
    assert q.reliability == 0.97 and q.relevance > 0.9 and q.overall > 0.85
    labels = describe_quality("https://www.nseindia.com/indices", date(2024, 9, 30), q, as_of=TODAY)
    assert labels["reliability"] == "High: Stock exchange"
    assert labels["recency"].endswith("2 years ago")
    assert labels["relevance"].startswith("High: talks directly")
    low = SourceQuality(reliability=0.15, recency=0.5, relevance=0.1)
    assert describe_quality("https://x.com/a", None, low, as_of=TODAY)["recency"] == (
        "Medium: Publication date unknown"
    )


def test_return_promises_find_guarantee_cautions_relevant_across_languages():
    c = claim(
        "Mere group mein guaranteed 5% har mahine milega, bilkul risk-free.",
        ClaimType.RETURN_PROMISE,
    )
    caution = "No one can guarantee fixed returns. Investments are subject to market risk."
    assert relevance_score(c, caution) >= 0.6
    assert relevance_score(c, "The monsoon arrived early this year.") < 0.2

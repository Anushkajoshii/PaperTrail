import json
from datetime import date

import httpx
import pytest
from pydantic import SecretStr

from papertrail.config import Settings
from papertrail.models import Claim, ClaimType
from papertrail.tools.search import (
    OfflineSearch,
    SearchError,
    SearchResult,
    TavilySearch,
    build_queries,
    get_search_provider,
    is_excluded,
    registrable_domain,
)


def claim(text, claim_type, tickers=()):
    return Claim(text=text, quote=text, claim_type=claim_type, tickers=list(tickers))


def test_registrable_domain_and_exclusions():
    assert registrable_domain("https://www.economictimes.indiatimes.com/a") == (
        "economictimes.indiatimes.com"
    )
    assert registrable_domain("https://m.youtube.com/watch?v=1") == "youtube.com"
    assert is_excluded("https://youtu.be/abc") and is_excluded("https://music.youtube.com/x")
    assert not is_excluded("https://www.nseindia.com/") and not is_excluded(
        "https://notyoutube.com"
    )


def test_build_queries_by_claim_type():
    q = build_queries(
        claim("TATAMOTORS gave 300% in 2023.", ClaimType.PAST_PERFORMANCE, ["TATAMOTORS"])
    )
    assert q == ["TATAMOTORS gave 300% in 2023", "TATAMOTORS NSE share price history 2023"]
    cred = build_queries(
        claim("The speaker is SEBI registered.", ClaimType.CREDENTIAL), creator_name="Demo Creator"
    )
    assert "Demo Creator" in cred[1]
    promise = build_queries(claim("Guaranteed 5% monthly.", ClaimType.RETURN_PROMISE))
    assert "guaranteed" in promise[1]
    other = build_queries(claim("Something with 5 numbers.", ClaimType.OTHER))
    assert other == ["Something with 5 numbers"]


def test_search_result_lenient_dates():
    r = SearchResult(url="https://a.test/x", published_date="2024-09-30T10:00:00Z")
    assert r.published_date == date(2024, 9, 30)
    assert SearchResult(url="https://a.test/x", published_date="last week").published_date is None


def test_offline_search_finds_demo_results_and_drops_social():
    results = OfflineSearch().search("TATAMOTORS share price target youtube video channel")
    urls = [str(r.url) for r in results]
    assert urls[0] == "https://exchange.demo.test/quotes/TATAMOTORS"
    assert not any("youtube" in u for u in urls)
    assert all(u.split("/")[2].endswith(".test") for u in urls)  # demo data only
    assert OfflineSearch().search("completely unrelated cooking recipe") == []


def test_tavily_request_and_parsing():
    seen = {}

    def handler(request: httpx.Request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://www.nseindia.com/x",
                        "title": "NSE",
                        "content": "data",
                        "published_date": "2024-10-01",
                        "score": 0.9,
                    },
                    {
                        "url": "https://www.youtube.com/watch?v=1",
                        "title": "vid",
                        "content": "claim",
                    },
                    {"title": "missing url"},
                    {"url": "https://www.nseindia.com/x/", "title": "dup"},
                ]
            },
        )

    tavily = TavilySearch("tvly-test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    results = tavily.search("nifty all time high", max_results=5)
    assert [str(r.url) for r in results] == ["https://www.nseindia.com/x"]
    assert seen["auth"] == "Bearer tvly-test"
    assert seen["body"]["query"] == "nifty all time high"
    assert "youtube.com" in seen["body"]["exclude_domains"]


def test_tavily_errors():
    bad = TavilySearch(
        "k", client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    )
    with pytest.raises(SearchError, match="429"):
        bad.search("x")


def test_provider_selection():
    assert get_search_provider(Settings(_env_file=None)).name == "offline"
    with pytest.raises(SearchError, match="TAVILY_API_KEY"):
        get_search_provider(Settings(_env_file=None, search_provider="tavily"))
    live = Settings(_env_file=None, search_provider="tavily", tavily_api_key=SecretStr("k"))
    assert get_search_provider(live).name == "tavily"
    with pytest.raises(SearchError, match="Unknown"):
        get_search_provider(Settings(_env_file=None, search_provider="bing"))

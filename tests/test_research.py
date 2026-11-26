from datetime import date

from papertrail.agent.research import ResearchDeps, queries_for_round, research_claim
from papertrail.models import Claim, ClaimType, SourceType
from papertrail.tools.fetch import FetchedPage, FetchError
from papertrail.tools.search import OfflineSearch, SearchError, SearchResult

TODAY = date(2026, 11, 26)


def claim(text, claim_type=ClaimType.MARKET_FACT, tickers=()):
    return Claim(id="clm_abc", text=text, quote=text, claim_type=claim_type, tickers=list(tickers))


class FixedSearch:
    name = "fixed"

    def __init__(self, results, fail=False):
        self.results, self.fail, self.queries = results, fail, []

    def search(self, query, *, max_results=5):
        self.queries.append(query)
        if self.fail:
            raise SearchError("quota exceeded")
        return self.results[:max_results]


class FakeFetcher:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def fetch(self, url):
        self.calls.append(url)
        if url not in self.pages:
            raise FetchError("HTTP 403")
        return FetchedPage(
            url=url,
            final_url=url,
            title="t",
            site_name="Example News",
            published=date(2024, 10, 2),
            text=self.pages[url],
        )


def test_offline_research_finds_demo_evidence_with_quality():
    c = claim("Nifty 50 hit an all-time high of 26,277 on 27 September 2024.")
    r = research_claim(c, ResearchDeps(search=OfflineSearch(), today=TODAY))
    assert r.candidates and r.has_enough
    top = r.candidates[0]
    assert top.source_type is SourceType.EXCHANGE and "26,277" in top.snippet
    assert top.quality_labels["reliability"].endswith("(demo data)")
    assert top.id.startswith("evd_abc_") and r.pages_fetched == 0  # demo results are not fetched


def test_live_style_research_fetches_pages_and_falls_back_to_snippets():
    results = [
        SearchResult(url="https://www.nseindia.com/a", title="NSE", snippet="Nifty data snippet"),
        SearchResult(
            url="https://www.livemint.com/b",
            title="Mint",
            snippet="Nifty 50 hit 26,277 on 27 September 2024 (snippet).",
        ),
        SearchResult(url="https://blog.example.com/c", title="Blog", snippet="Nifty 26,277 high"),
    ]
    fetcher = FakeFetcher(
        {
            "https://www.nseindia.com/a": "Intro text. The Nifty 50 hit an all-time high "
            "of 26,277 on 27 September 2024. Other news."
        }
    )
    deps = ResearchDeps(search=FixedSearch(results), fetcher=fetcher, pages_to_fetch=2, today=TODAY)
    r = research_claim(claim("Nifty 50 hit an all-time high of 26,277 on 27 September 2024."), deps)
    assert fetcher.calls == ["https://www.nseindia.com/a", "https://www.livemint.com/b"]
    assert r.pages_fetched == 1 and any("403" in e for e in r.errors)
    nse = next(c for c in r.candidates if "nseindia" in str(c.url))
    assert "all-time high of 26,277" in nse.snippet and nse.publisher == "Example News"
    assert any("snippet" in c.snippet for c in r.candidates)  # fallback used for the 403 page


def test_irrelevant_results_are_dropped_and_duplicates_skipped():
    results = [
        SearchResult(url="https://x.test/1", title="Cooking", snippet="How to bake bread."),
        SearchResult(url="https://x.test/1", title="dup", snippet="dup"),
    ]
    r = research_claim(claim("Nifty 50 hit 26,277."), ResearchDeps(search=FixedSearch(results)))
    assert r.candidates == [] and not r.has_enough


def test_search_errors_are_recorded_not_raised():
    r = research_claim(claim("Nifty 50 hit 26,277."), ResearchDeps(search=FixedSearch([], True)))
    assert r.candidates == [] and "quota exceeded" in r.errors[0]


def test_round_two_uses_broader_queries_and_keeps_round_one_results():
    c = claim("TATAMOTORS will hit ₹1500 by March.", ClaimType.STOCK_CALL, ["TATAMOTORS"])
    assert queries_for_round(c, 2) == ["tatamotors will ₹1500 march", "TATAMOTORS latest news"]
    first = research_claim(c, ResearchDeps(search=OfflineSearch(), today=TODAY))
    second = research_claim(
        c, ResearchDeps(search=OfflineSearch(), today=TODAY), round_no=2, previous=first
    )
    assert second.queries[-1] == "TATAMOTORS latest news"
    assert len({str(x.url) for x in second.candidates}) == len(second.candidates)

"""Research step: find candidate evidence for one claim.

query -> search -> (safe) fetch of the top pages -> most relevant passages -> quality scores.

The agent calls this up to ``max_search_rounds`` times per claim. Round 2 uses broader queries
and only runs if round 1 found nothing clearly relevant (the evidence loop, ADR-010). The URLs to
read are chosen here, in code: page text can never make the agent fetch something else.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from papertrail.agent.judge import EvidenceCandidate
from papertrail.models import Claim
from papertrail.observability.tracing import span
from papertrail.text import normalize_for_match
from papertrail.tools.fetch import FetchError, PageFetcher
from papertrail.tools.search import SearchError, SearchProvider, SearchResult, build_queries
from papertrail.tools.source_quality import (
    assess_source,
    best_passages,
    classify_source,
    describe_quality,
)

log = logging.getLogger(__name__)

MIN_RELEVANCE = 0.2  # below this a passage is not worth the judge's time
ENOUGH_RELEVANCE = 0.45  # at least one passage this relevant ends the search loop
MAX_CANDIDATES = 5


@dataclass
class ResearchDeps:
    search: SearchProvider
    fetcher: PageFetcher | None = None
    max_results: int = 5
    pages_to_fetch: int = 2
    today: date = field(default_factory=date.today)


@dataclass
class ResearchResult:
    candidates: list[EvidenceCandidate] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    pages_fetched: int = 0

    @property
    def has_enough(self) -> bool:
        return any(c.quality.relevance >= ENOUGH_RELEVANCE for c in self.candidates)


def queries_for_round(claim: Claim, round_no: int, creator_name: str | None = None) -> list[str]:
    if round_no <= 1:
        return build_queries(claim, creator_name=creator_name)
    # Round 2: broader wording, built from the claim's key terms.
    words = [w for w in normalize_for_match(claim.text).split() if len(w) > 3][:8]
    broader = [" ".join(words)]
    if claim.tickers:
        broader.append(f"{claim.tickers[0]} latest news")
    return [q for q in dict.fromkeys(broader) if q]


def _passages_for(
    result: SearchResult, claim: Claim, deps: ResearchDeps, budget: list[int], out: ResearchResult
) -> tuple[list[str], date | None, str | None]:
    """Return (passages, published date, site name) for one search result."""
    url = str(result.url)
    demo = url.split("/")[2].endswith(".test")
    if deps.fetcher is not None and not demo and budget[0] > 0:
        budget[0] -= 1
        try:
            with span("fetch", input={"url": url}):
                page = deps.fetcher.fetch(url)
            out.pages_fetched += 1
            passages = best_passages(claim, page.text, k=1) or []
            return (
                passages or [result.snippet],
                page.published or result.published_date,
                (page.site_name),
            )
        except FetchError as exc:
            out.errors.append(f"Could not read {url}: {exc}")
    passages = best_passages(claim, result.snippet, k=1) or [result.snippet]
    return passages, result.published_date, None


def research_claim(
    claim: Claim,
    deps: ResearchDeps,
    *,
    round_no: int = 1,
    creator_name: str | None = None,
    previous: ResearchResult | None = None,
) -> ResearchResult:
    out = previous or ResearchResult()
    seen = {str(c.url) for c in out.candidates}
    budget = [deps.pages_to_fetch]
    counter = len(out.candidates)
    for query in queries_for_round(claim, round_no, creator_name):
        out.queries.append(query)
        try:
            with span("search", input={"query": query}, metadata={"round": round_no}) as sp:
                results = deps.search.search(query, max_results=deps.max_results)
                if sp is not None:
                    sp.output = [{"title": r.title, "url": str(r.url)} for r in results]
        except SearchError as exc:
            out.errors.append(f"Search failed for '{query}': {exc}")
            continue
        for r in results:
            url = str(r.url)
            if url in seen or not (r.snippet or r.title):
                continue
            seen.add(url)
            passages, published, site = _passages_for(r, claim, deps, budget, out)
            for passage in passages:
                if not passage.strip():
                    continue
                source_type, quality = assess_source(
                    url, published, claim, passage, as_of=deps.today
                )
                if quality.relevance < MIN_RELEVANCE:
                    continue
                counter += 1
                out.candidates.append(
                    EvidenceCandidate(
                        id=f"evd_{claim.id.removeprefix('clm_')}_{counter}",
                        claim_id=claim.id,
                        url=url,
                        title=r.title or url,
                        publisher=site or classify_source(url).label,
                        published_at=published,
                        source_type=source_type,
                        snippet=passage[:1200],
                        quality=quality,
                        quality_labels=describe_quality(url, published, quality, as_of=deps.today),
                    )
                )
    out.candidates.sort(key=lambda c: -c.quality.overall)
    del out.candidates[MAX_CANDIDATES:]
    return out

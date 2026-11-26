"""Web search for evidence.

* ``TavilySearch``: live search through the Tavily API (free tier is enough for this project).
* ``OfflineSearch``: a tiny built-in fixture of clearly labelled demo results on ``.test``
  domains, so the pipeline runs end to end with no keys. It is never mistaken for real evidence.

Results from social platforms are dropped. A YouTube video repeating a claim is more of the
claim, not evidence for it.
"""

from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, HttpUrl, field_validator

from papertrail.models import Claim, ClaimType
from papertrail.text import normalize_for_match

TAVILY_URL = "https://api.tavily.com/search"

# Never evidence: the content being checked usually lives here.
EXCLUDED_DOMAINS = frozenset(
    {
        "youtube.com",
        "youtu.be",
        "instagram.com",
        "facebook.com",
        "x.com",
        "twitter.com",
        "t.me",
        "telegram.me",
        "telegram.org",
        "whatsapp.com",
        "tiktok.com",
        "threads.net",
        "linkedin.com",
    }
)


class SearchError(RuntimeError):
    pass


class SearchResult(BaseModel):
    url: HttpUrl
    title: str = ""
    snippet: str = ""
    published_date: date | None = None
    score: float | None = Field(default=None, description="Search engine's own relevance score")

    @field_validator("published_date", mode="before")
    @classmethod
    def _lenient_date(cls, v: object) -> object:
        if isinstance(v, str):
            m = re.match(r"(\d{4}-\d{2}-\d{2})", v.strip())
            return m.group(1) if m else None
        return v

    @property
    def domain(self) -> str:
        return registrable_domain(str(self.url))


def registrable_domain(url: str) -> str:
    """'https://www.economictimes.indiatimes.com/x' -> 'economictimes.indiatimes.com'."""
    host = (urlparse(url).hostname or "").lower()
    return host.removeprefix("www.").removeprefix("m.")


def is_excluded(url: str) -> bool:
    domain = registrable_domain(url)
    return any(domain == d or domain.endswith("." + d) for d in EXCLUDED_DOMAINS)


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]: ...


# ------------------------------------------------------------------------------------------
# Query building
# ------------------------------------------------------------------------------------------

_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def build_queries(claim: Claim, *, creator_name: str | None = None) -> list[str]:
    """Two or three focused queries per claim. Shorter, targeted queries beat one long one."""
    base = claim.text.rstrip(".")
    queries = [base]
    ticker = claim.tickers[0] if claim.tickers else None
    years = " ".join(m.group(0) for m in _YEAR.finditer(claim.text))
    match claim.claim_type:
        case ClaimType.PAST_PERFORMANCE | ClaimType.STOCK_CALL if ticker:
            queries.append(f"{ticker} NSE share price history {years}".strip())
        case ClaimType.COMPANY_FACT if ticker:
            queries.append(f"{ticker} quarterly results {years} exchange filing".strip())
        case ClaimType.MARKET_FACT:
            queries.append(f"{base} NSE official data")
        case ClaimType.CREDENTIAL:
            who = creator_name or "investment adviser"
            queries.append(f"SEBI registered intermediaries {who} registration")
        case ClaimType.RETURN_PROMISE:
            queries.append("SEBI investor caution guaranteed assured returns")
    return list(dict.fromkeys(q for q in queries if q))


# ------------------------------------------------------------------------------------------
# Providers
# ------------------------------------------------------------------------------------------


def _filter(results: list[SearchResult], max_results: int) -> list[SearchResult]:
    seen: set[str] = set()
    kept = []
    for r in results:
        key = str(r.url).rstrip("/")
        if is_excluded(key) or key in seen:
            continue
        seen.add(key)
        kept.append(r)
    return kept[:max_results]


class TavilySearch:
    name = "tavily"

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=20.0)
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        try:
            resp = self._client.post(
                TAVILY_URL,
                headers=self._headers,
                json={
                    "query": query,
                    "max_results": max_results + 3,  # room for excluded domains
                    "search_depth": "basic",
                    "exclude_domains": sorted(EXCLUDED_DOMAINS),
                },
            )
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPStatusError as exc:
            raise SearchError(f"Tavily HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise SearchError(f"Tavily connection error: {exc}") from exc
        results = []
        for item in body.get("results") or []:
            try:
                results.append(
                    SearchResult(
                        url=item["url"],
                        title=item.get("title") or "",
                        snippet=item.get("content") or "",
                        published_date=item.get("published_date"),
                        score=item.get("score"),
                    )
                )
            except (KeyError, ValueError):
                continue  # skip malformed entries rather than fail the whole search
        return _filter(results, max_results)


@lru_cache
def _offline_fixture() -> list[dict]:
    path = Path(__file__).parent / "data" / "offline_search.json"
    return json.loads(path.read_text(encoding="utf-8"))["results"]


class OfflineSearch:
    """Keyword match against the demo fixture. Deterministic and free."""

    name = "offline"

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        words = set(normalize_for_match(query).split())
        scored = []
        for entry in _offline_fixture():
            hits = sum(1 for k in entry["keywords"] if normalize_for_match(k) in words)
            if hits >= 2:
                scored.append((hits, entry))
        scored.sort(key=lambda he: -he[0])
        results = [
            SearchResult(
                url=e["url"],
                title=e["title"],
                snippet=e["content"],
                published_date=e.get("published_date"),
                score=hits / len(e["keywords"]),
            )
            for hits, e in scored
        ]
        return _filter(results, max_results)


def get_search_provider(settings) -> SearchProvider:
    if settings.search_provider == "tavily":
        if not settings.tavily_api_key:
            raise SearchError("Set PAPERTRAIL_TAVILY_API_KEY to use live search")
        return TavilySearch(settings.tavily_api_key.get_secret_value())
    if settings.search_provider == "offline":
        return OfflineSearch()
    raise SearchError(f"Unknown search provider '{settings.search_provider}'")

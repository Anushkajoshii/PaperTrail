"""Daily share prices for settling stock calls.

* ``none`` (default): no prices, so calls stay "no data" rather than being settled with
  anything made up.
* ``offline``: demo prices for the fictional symbols used in tests and evals (KESTREL,
  ORIONBANK, LOTUSFOOD). They are never real companies, so fake numbers can't be mistaken for
  real ones.
* ``alphavantage``: Alpha Vantage daily prices for BSE listings (free key, 25 requests a day).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import httpx

DEMO_PRICES = Path(__file__).parent / "data" / "demo_prices.json"


class PriceError(RuntimeError):
    """The price service failed or refused (e.g. the daily limit). Try again later."""


@dataclass(frozen=True)
class PricePoint:
    day: date
    high: float
    low: float
    close: float


class PriceProvider(Protocol):
    source: str

    def daily(self, ticker: str, since: date) -> list[PricePoint]:
        """Daily prices from ``since`` to the latest available, oldest first. [] if unknown."""
        ...


class NoPrices:
    source = "none"

    def daily(self, ticker: str, since: date) -> list[PricePoint]:
        return []


class OfflinePrices:
    source = "Demo prices for fictional symbols (not real market data)"

    def __init__(self, path: Path = DEMO_PRICES) -> None:
        self._data = _load_demo(str(path))

    def daily(self, ticker: str, since: date) -> list[PricePoint]:
        return [p for p in self._data.get(ticker.upper(), []) if p.day >= since]


@lru_cache
def _load_demo(path: str) -> dict[str, list[PricePoint]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        t: [PricePoint(date.fromisoformat(d), h, lo, c) for d, h, lo, c in rows]
        for t, rows in raw["series"].items()
    }


class AlphaVantagePrices:
    source = "Alpha Vantage daily prices (BSE)"
    URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._key = api_key
        self._client = client or httpx.Client(timeout=20.0)

    def daily(self, ticker: str, since: date) -> list[PricePoint]:
        try:
            resp = self._client.get(
                self.URL,
                params={
                    "function": "TIME_SERIES_DAILY",
                    "symbol": f"{ticker.upper()}.BSE",
                    "outputsize": "compact",  # about the last 100 trading days
                    "apikey": self._key,
                },
            )
            resp.raise_for_status()
            body = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PriceError(f"Price service unavailable: {exc}") from exc
        if "Error Message" in body:
            return []  # unknown symbol
        if "Time Series (Daily)" not in body:  # "Note"/"Information": rate limit or key problem
            raise PriceError(str(body.get("Note") or body.get("Information") or "No data")[:200])
        points = [
            PricePoint(
                date.fromisoformat(d),
                float(v["2. high"]),
                float(v["3. low"]),
                float(v["4. close"]),
            )
            for d, v in body["Time Series (Daily)"].items()
        ]
        return sorted((p for p in points if p.day >= since), key=lambda p: p.day)


def get_price_provider(settings) -> PriceProvider:
    match settings.price_provider:
        case "offline":
            return OfflinePrices()
        case "alphavantage":
            if not settings.alphavantage_api_key:
                return NoPrices()
            return AlphaVantagePrices(settings.alphavantage_api_key.get_secret_value())
        case _:
            return NoPrices()

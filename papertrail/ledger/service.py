"""Ledger operations: start tracking calls from a finished check, and the daily re-check."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta

from papertrail.ledger.models import LedgerEntry, LedgerStatus
from papertrail.ledger.parse import parse_prediction
from papertrail.ledger.prices import PriceError, PriceProvider
from papertrail.ledger.settle import settle
from papertrail.ledger.store import LedgerStore
from papertrail.models import Check, CheckStatus
from papertrail.store.checks import normalize_handle

log = logging.getLogger(__name__)

# Calls without price data are retried for this long after their deadline, then left as is.
NO_DATA_GRACE = timedelta(days=30)


def entry_id(claim_id: str) -> str:
    return "led_" + claim_id.removeprefix("clm_")


def track_check(check: Check, store: LedgerStore, today: date | None = None) -> list[LedgerEntry]:
    """Add every trackable stock call in a completed check. Safe to repeat."""
    if check.status is not CheckStatus.COMPLETED:
        return []
    made_on = today or check.created_at.date()
    creator = normalize_handle(check.input.creator_handle) if check.input.creator_handle else None
    added = []
    for claim in check.claims:
        prediction = parse_prediction(claim, made_on)
        if prediction is None or store.get(entry_id(claim.id)) is not None:
            continue
        entry = LedgerEntry(
            id=entry_id(claim.id),
            check_id=check.id,
            claim_id=claim.id,
            creator=creator,
            ticker=prediction.ticker,
            claim_text=claim.text,
            quote=claim.quote,
            direction=prediction.direction,
            target_price=prediction.target_price,
            target_pct=prediction.target_pct,
            made_on=made_on,
            due_on=prediction.due_on,
            deadline_stated=prediction.deadline_stated,
            note="Tracking started. Prices are checked daily.",
        )
        store.save(entry)
        added.append(entry)
    return added


def run_daily(
    store: LedgerStore, prices: PriceProvider, today: date, *, max_tickers: int = 20
) -> dict[str, int]:
    """Re-check every active call. Each symbol is fetched once (free price APIs are rationed)."""
    by_ticker: dict[str, list[LedgerEntry]] = defaultdict(list)
    for e in store.list_active():
        if e.status is LedgerStatus.NO_DATA and today > e.due_on + NO_DATA_GRACE:
            continue
        by_ticker[e.ticker].append(e)
    summary: dict[str, int] = defaultdict(int)
    for ticker in sorted(by_ticker)[:max_tickers]:
        entries = by_ticker[ticker]
        try:
            points = prices.daily(ticker, since=min(e.made_on for e in entries))
        except PriceError as exc:
            log.warning("Prices for %s unavailable: %s", ticker, exc)
            summary["price_errors"] += 1
            continue
        for e in entries:
            updated = settle(e, points, today, prices.source)
            store.save(updated)
            summary[updated.status.value] += 1
    summary["tickers"] = min(len(by_ticker), max_tickers)
    summary["skipped_tickers"] = max(0, len(by_ticker) - max_tickers)
    return dict(summary)

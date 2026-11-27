"""Settle a tracked call against daily prices: hit, missed, still open, or no data.

Rules (stated in plain language on the site, see docs/LEDGER.md):
* **Hit**: on some day between the start of tracking and the deadline, the day's high reached
  the target (the day's low, for a call that the price will fall).
* **Missed**: the deadline has passed, prices cover the whole period, and the target was
  never reached.
* **Open**: neither yet.
* **No data**: we have no prices for the symbol.
Tracking starts when PaperTrail first saw the call, which may be after it was made.
"""

from __future__ import annotations

from datetime import date, timedelta

from papertrail.ledger.models import Direction, LedgerEntry, LedgerStatus
from papertrail.ledger.prices import PricePoint

# Prices may stop a few days short of the deadline (weekends, holidays).
COVERAGE_SLACK = timedelta(days=5)


def settle(entry: LedgerEntry, points: list[PricePoint], today: date, source: str) -> LedgerEntry:
    if entry.status in (LedgerStatus.HIT, LedgerStatus.MISSED):
        return entry
    update: dict = {"last_checked": today}
    tracked = [p for p in points if p.day >= entry.made_on]
    if not tracked:
        return entry.model_copy(
            update=update
            | {
                "status": LedgerStatus.NO_DATA,
                "note": "No price data for this symbol yet, so the call can't be settled.",
            }
        )
    update |= {"price_source": source, "last_price": tracked[-1].close}
    baseline = entry.baseline_price or tracked[0].close
    update["baseline_price"] = baseline
    direction = entry.direction
    if entry.target_price is not None:
        # A target below the starting price only makes sense as a call that the price will fall.
        direction = Direction.DOWN if entry.target_price < baseline else Direction.UP
    update["direction"] = direction
    target = entry.model_copy(update=update).resolved_target()
    if target is None:
        return entry.model_copy(update=update | {"status": LedgerStatus.NO_DATA})

    window = [p for p in tracked if p.day <= entry.due_on]
    up = direction is Direction.UP
    if window:
        update["best_price"] = max(p.high for p in window) if up else min(p.low for p in window)
    for p in window:
        if (up and p.high >= target) or (not up and p.low <= target):
            return entry.model_copy(
                update=update
                | {
                    "status": LedgerStatus.HIT,
                    "hit_on": p.day,
                    "note": f"Reached ₹{target:,.2f} on {p.day:%d %b %Y}.",
                }
            )
    covered = bool(window) and window[-1].day >= entry.due_on - COVERAGE_SLACK
    if today > entry.due_on and covered:
        best = update.get("best_price")
        return entry.model_copy(
            update=update
            | {
                "status": LedgerStatus.MISSED,
                "note": f"Did not reach ₹{target:,.2f} by {entry.due_on:%d %b %Y}"
                + (f" (closest: ₹{best:,.2f})." if best else "."),
            }
        )
    return entry.model_copy(
        update=update
        | {
            "status": LedgerStatus.OPEN,
            "note": f"Target ₹{target:,.2f}; last price ₹{tracked[-1].close:,.2f}.",
        }
    )

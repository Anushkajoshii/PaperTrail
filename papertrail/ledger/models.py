"""Claim Ledger records: one stock call (a price target with a deadline), tracked until it can
be settled against real prices."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field

from papertrail.models import _Model


class Direction(StrEnum):
    UP = "up"  # target above the price when the call was made ("will reach ₹1500")
    DOWN = "down"  # target below it ("will fall to ₹500")


class LedgerStatus(StrEnum):
    OPEN = "open"  # deadline not reached yet and target not hit so far
    HIT = "hit"  # the price reached the target on or before the deadline
    MISSED = "missed"  # the deadline passed without the price reaching the target
    NO_DATA = "no_data"  # no price data for this symbol (yet), so it cannot be settled


LEDGER_STATUS_DESCRIPTIONS: dict[LedgerStatus, str] = {
    LedgerStatus.OPEN: "Still running: the deadline has not passed and the target is not hit yet.",
    LedgerStatus.HIT: "The price reached the target on or before the deadline.",
    LedgerStatus.MISSED: "The deadline passed and the price never reached the target.",
    LedgerStatus.NO_DATA: "We have no price data for this symbol, so it cannot be settled.",
}


class LedgerEntry(_Model):
    id: str = Field(description="led_ + the claim id, so a call is tracked once.")
    check_id: str
    claim_id: str
    creator: str | None = Field(default=None, description="Normalised handle, without '@'.")
    ticker: str
    claim_text: str
    quote: str
    direction: Direction = Direction.UP
    target_price: float | None = Field(default=None, gt=0, description="Target in rupees.")
    target_pct: float | None = Field(
        default=None, description="Target as a % move from the starting price, if given that way."
    )
    made_on: date = Field(description="When PaperTrail first saw the call (tracking starts).")
    due_on: date = Field(description="The deadline: stated, or a default horizon if none was.")
    deadline_stated: bool = Field(description="False when no deadline was given.")
    baseline_price: float | None = Field(
        default=None, description="Closing price on (or just after) the day tracking started."
    )
    status: LedgerStatus = LedgerStatus.OPEN
    hit_on: date | None = None
    best_price: float | None = Field(
        default=None, description="Closest the price came to the target while tracking."
    )
    last_price: float | None = None
    last_checked: date | None = None
    price_source: str | None = None
    note: str = ""

    def resolved_target(self) -> float | None:
        """The target in rupees, working out % targets from the starting price."""
        if self.target_price is not None:
            return self.target_price
        if self.target_pct is not None and self.baseline_price:
            sign = 1 if self.direction is Direction.UP else -1
            return round(self.baseline_price * (1 + sign * abs(self.target_pct) / 100), 2)
        return None

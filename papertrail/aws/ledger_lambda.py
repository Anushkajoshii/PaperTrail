"""Daily Claim Ledger job (EventBridge schedule -> Lambda): re-check every open stock call."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from papertrail.aws.secrets import load_secrets_from_env
from papertrail.config import get_settings
from papertrail.ledger.prices import get_price_provider
from papertrail.ledger.service import run_daily
from papertrail.ledger.store import get_ledger_store

log = logging.getLogger("papertrail.ledger")
logging.getLogger().setLevel(logging.INFO)


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, int]:
    load_secrets_from_env()
    s = get_settings()
    summary = run_daily(
        get_ledger_store(s),
        get_price_provider(s),
        datetime.now(UTC).date(),
        max_tickers=s.ledger_max_tickers_per_run,
    )
    log.info("Ledger run: %s", summary)
    return summary

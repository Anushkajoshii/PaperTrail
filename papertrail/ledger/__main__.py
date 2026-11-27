"""Run the daily ledger re-check by hand:  make ledger   (or python -m papertrail.ledger)"""

import json
import logging
import sys
from datetime import date

from papertrail.config import get_settings
from papertrail.ledger.prices import get_price_provider
from papertrail.ledger.service import run_daily
from papertrail.ledger.store import get_ledger_store


def main() -> int:  # pragma: no cover - thin CLI
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    s = get_settings()
    summary = run_daily(
        get_ledger_store(s),
        get_price_provider(s),
        date.today(),
        max_tickers=s.ledger_max_tickers_per_run,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

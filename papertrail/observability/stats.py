"""Operational summary of recent checks: speed, cost and reliability.

    make stats         # checks in the local store
    make stats-prod    # checks in the deployed DynamoDB table (needs `aws login`)

Percentiles use the nearest-rank method. Only finished checks are counted.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from collections.abc import Iterable, Sequence

from pydantic import BaseModel

from papertrail.models import Check, CheckStatus


def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


class Stats(BaseModel):
    checks: int
    completed: int
    failed: int
    failure_rate: float
    p50_seconds: float
    p95_seconds: float
    mean_ai_calls: float
    mean_tokens: float
    p95_tokens: float
    mean_cost_usd: float
    total_cost_usd: float
    providers: dict[str, int]
    slowest_step: str | None


def summarize(checks: Iterable[Check]) -> Stats:
    done = [c for c in checks if c.status in (CheckStatus.COMPLETED, CheckStatus.FAILED)]
    ok = [c for c in done if c.status is CheckStatus.COMPLETED and c.metrics]
    secs = [c.metrics.duration_ms / 1000 for c in ok]
    tokens = [float(c.metrics.total_tokens) for c in ok]
    costs = [c.metrics.cost_usd for c in ok]
    step_totals: Counter[str] = Counter()
    for c in ok:
        step_totals.update(c.metrics.step_ms)
    n = len(ok) or 1
    return Stats(
        checks=len(done),
        completed=len(ok),
        failed=len(done) - len(ok),
        failure_rate=round((len(done) - len(ok)) / len(done), 3) if done else 0.0,
        p50_seconds=round(percentile(secs, 50), 1),
        p95_seconds=round(percentile(secs, 95), 1),
        mean_ai_calls=round(sum(c.metrics.llm_calls for c in ok) / n, 1),
        mean_tokens=round(sum(tokens) / n),
        p95_tokens=percentile(tokens, 95),
        mean_cost_usd=round(sum(costs) / n, 6),
        total_cost_usd=round(sum(costs), 6),
        providers=dict(Counter(c.metrics.llm_provider or "unknown" for c in ok)),
        slowest_step=step_totals.most_common(1)[0][0] if step_totals else None,
    )


def to_markdown(s: Stats) -> str:
    providers = ", ".join(f"{k} ({v})" for k, v in sorted(s.providers.items())) or "-"
    rows = [
        ("Checks (completed / failed)", f"{s.completed} / {s.failed}"),
        ("Failure rate", f"{s.failure_rate:.1%}"),
        ("Time per check, p50 / p95", f"{s.p50_seconds} s / {s.p95_seconds} s"),
        ("AI calls per check (mean)", f"{s.mean_ai_calls}"),
        ("Tokens per check, mean / p95", f"{s.mean_tokens:,.0f} / {s.p95_tokens:,.0f}"),
        ("Cost per check (mean)", f"${s.mean_cost_usd:.4f}"),
        ("Providers", providers),
        ("Slowest step overall", s.slowest_step or "-"),
    ]
    return "| Metric | Value |\n|---|---|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - thin CLI
    from papertrail.config import get_settings
    from papertrail.store import get_check_store

    parser = argparse.ArgumentParser(description="Speed, cost and reliability of recent checks")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    stats = summarize(get_check_store(get_settings()).list_recent(args.limit))
    print(json.dumps(stats.model_dump(), indent=2) if args.json else to_markdown(stats))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

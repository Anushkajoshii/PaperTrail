import pytest

from papertrail.models import Check, CheckInput, CheckMetrics, CheckStatus, InputKind
from papertrail.observability.stats import percentile, summarize, to_markdown
from papertrail.store import MemoryCheckStore, SqliteCheckStore

INPUT = CheckInput(kind=InputKind.TEXT, text="Nifty hit 26,000.")


def done(seconds, tokens=1000, cost=0.0, provider="groq", steps=None):
    return Check(
        input=INPUT,
        status=CheckStatus.COMPLETED,
        metrics=CheckMetrics(
            llm_calls=5,
            total_tokens=tokens,
            cost_usd=cost,
            duration_ms=seconds * 1000,
            llm_provider=provider,
            step_ms=steps or {"judge": seconds * 600, "extract": seconds * 300},
        ),
    )


def test_percentile_nearest_rank():
    assert percentile([], 50) == 0.0
    assert percentile([3, 1, 2], 50) == 2
    assert percentile(list(range(1, 101)), 95) == 95
    assert percentile([5], 95) == 5


def test_summary_of_completed_failed_and_running_checks():
    checks = [done(s, tokens=1000 * s, cost=0.001 * s) for s in (2, 4, 6, 8, 30)]
    checks += [
        Check(input=INPUT, status=CheckStatus.FAILED, error="boom"),
        Check(input=INPUT, status=CheckStatus.RESEARCHING),  # still running: ignored
    ]
    s = summarize(checks)
    assert (s.checks, s.completed, s.failed) == (6, 5, 1)
    assert s.failure_rate == pytest.approx(1 / 6, abs=1e-3)
    assert s.p50_seconds == 6 and s.p95_seconds == 30
    assert s.mean_ai_calls == 5 and s.mean_tokens == 10000 and s.p95_tokens == 30000
    assert s.mean_cost_usd == pytest.approx(0.01) and s.providers == {"groq": 5}
    assert s.slowest_step == "judge"
    md = to_markdown(s)
    assert "| Time per check, p50 / p95 | 6.0 s / 30.0 s |" in md and "groq (5)" in md


def test_empty_summary():
    s = summarize([])
    assert s.checks == 0 and s.failure_rate == 0 and s.slowest_step is None
    assert "| Providers | - |" in to_markdown(s)


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_list_recent_is_newest_first(backend, tmp_path):
    store = MemoryCheckStore() if backend == "memory" else SqliteCheckStore(tmp_path / "s.db")
    checks = [done(s) for s in (1, 2, 3)]
    for c in checks:
        store.save(c)
    assert [c.id for c in store.list_recent(2)] == [checks[2].id, checks[1].id]

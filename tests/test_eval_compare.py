import json

import pytest

from papertrail.evaluation.compare import _load, render


def report(name, provider, model, acc, recall, n=95, claims=55):
    per_class = {
        k: {"precision": 0.5, "recall": 0.5, "f1": 0.5}
        for k in ("supported", "contradicted", "misleading", "not_verifiable")
    }
    return {
        "_name": name,
        "provider": provider,
        "models": {"extract": model, "judge": model},
        "created_at": "2026-11-27T12:00:00+00:00",
        "verdicts": {
            "n": n,
            "accuracy": acc,
            "macro_f1": 0.6,
            "ece": 0.1,
            "brier": 0.2,
            "stance_accuracy": 0.7,
            "citation_validity": 0.9,
            "errors": 1,
            "accusatory_rate": 0.0,
            "per_class": per_class,
            "by_language": {"en": acc, "hi": 0.5},
            "latency_ms_p50": 1500.0,
            "latency_ms_p95": 9000.0,
        },
        "extraction": {
            "transcripts": 20,
            "gold_claims": claims,
            "recall": recall,
            "recall_strict": recall - 0.1,
            "precision": 0.8,
            "forbidden_extractions": 0,
        },
        "cost": {"llm_calls": 120, "total_tokens": 150000, "total_usd": 0.0},
    }


def test_rows_are_ranked_and_labelled():
    md = render(
        [
            report("mock-full", "mock", "mock", 0.5, 0.6),
            report("g-120b", "groq", "openai/gpt-oss-120b", 0.8, 0.9),
        ]
    )
    assert md.index("groq: openai/gpt-oss-120b") < md.index("mock: mock")  # best first
    assert "| groq: openai/gpt-oss-120b | 80% | 0.60 |" in md
    assert "**not** an AI model" in md and "$0 (free tier)" in md
    assert "1.5 s / 9.0 s" in md and "| 50% |" in md  # Hindi accuracy column


def test_refuses_to_compare_different_golden_sets(tmp_path):
    with pytest.raises(ValueError, match="different golden sets"):
        render([report("a", "groq", "x", 0.5, 0.5, n=40), report("b", "groq", "y", 0.5, 0.5)])
    with pytest.raises(ValueError):
        render([])
    p = tmp_path / "run.json"
    p.write_text(json.dumps(report("ignored", "anthropic", "claude", 0.9, 0.9)))
    loaded = _load(p)
    assert loaded["_name"] == "run" and "$0.0000" in render([loaded])

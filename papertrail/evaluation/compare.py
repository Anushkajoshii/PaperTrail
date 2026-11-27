"""Compare eval runs side by side: one row per provider/model, same golden set.

    uv run python -m papertrail.evaluation.compare evals/reports/groq-*-full.json \\
        evals/reports/mock-full.json --out evals/reports/model-comparison.md

Every number comes from a saved report JSON, so the table can always be traced back to a run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LABELS = ["supported", "contradicted", "misleading", "not_verifiable"]


def _load(path: Path) -> dict:
    r = json.loads(path.read_text(encoding="utf-8"))
    r["_name"] = path.stem
    return r


def _model(r: dict) -> str:
    models = sorted(set(r["models"].values()))
    return f"{r['provider']}: {' + '.join(models)}"


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{x:.0%}"


def _f(x: float | None, digits: int = 2) -> str:
    return "-" if x is None else f"{x:.{digits}f}"


def render(reports: list[dict]) -> str:
    if not reports:
        raise ValueError("No reports to compare")
    sizes = {(r["verdicts"]["n"], r["extraction"]["gold_claims"]) for r in reports}
    if len(sizes) != 1:
        raise ValueError(f"Reports use different golden sets: {sorted(sizes)}")
    n_verdicts, n_claims = sizes.pop()
    ranked = sorted(reports, key=lambda r: (-r["verdicts"]["accuracy"], r["_name"]))
    lines = [
        "# Model comparison",
        "",
        f"Same golden set for every row: {n_verdicts} verdicts judged on fixed evidence and "
        f"{n_claims} gold claims in {reports[0]['extraction']['transcripts']} transcripts. "
        "Each row used one model for both extraction and judging. The `mock` row is the offline "
        "rule-based baseline, **not** an AI model.",
        "",
        "## Verdicts",
        "",
        "| Model | Accuracy | Macro-F1 | Calibration error (ECE, lower is better) | Brier | "
        "Evidence stance | Citation validity | Judge errors | Accusatory wording |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in ranked:
        v = r["verdicts"]
        lines.append(
            f"| {_model(r)} | {_pct(v['accuracy'])} | {_f(v['macro_f1'])} | {_f(v['ece'])} | "
            f"{_f(v['brier'])} | {_pct(v['stance_accuracy'])} | {_pct(v['citation_validity'])} | "
            f"{v['errors']} | {_pct(v['accusatory_rate'])} |"
        )
    lines += [
        "",
        "## F1 per verdict label",
        "",
        "| Model | " + " | ".join(LABELS) + " |",
        "|---|" + "---|" * len(LABELS),
    ]
    for r in ranked:
        pc = r["verdicts"]["per_class"]
        lines.append(f"| {_model(r)} | " + " | ".join(_f(pc[k]["f1"]) for k in LABELS) + " |")
    langs = sorted({lang for r in reports for lang in r["verdicts"]["by_language"]})
    lines += [
        "",
        "## Verdict accuracy by language",
        "",
        "| Model | " + " | ".join(langs) + " |",
        "|---|" + "---|" * len(langs),
    ]
    for r in ranked:
        bl = r["verdicts"]["by_language"]
        lines.append(f"| {_model(r)} | " + " | ".join(_pct(bl.get(x)) for x in langs) + " |")
    lines += [
        "",
        "## Claim extraction",
        "",
        "| Model | Recall | Recall with correct type | Precision | Forbidden extractions |",
        "|---|---|---|---|---|",
    ]
    for r in sorted(reports, key=lambda r: (-r["extraction"]["recall_strict"], r["_name"])):
        e = r["extraction"]
        lines.append(
            f"| {_model(r)} | {_pct(e['recall'])} | {_pct(e['recall_strict'])} | "
            f"{_pct(e['precision'])} | {e['forbidden_extractions']} |"
        )
    lines += [
        "",
        "## Speed and cost",
        "",
        "| Model | Verdict time p50 / p95 | AI calls | Tokens | Cost |",
        "|---|---|---|---|---|",
    ]
    for r in ranked:
        v, c = r["verdicts"], r["cost"]
        cost = (
            "$0 (free tier)"
            if r["provider"] in {"groq", "mock", "ollama"}
            else (f"${c['total_usd']:.4f}")
        )
        p50, p95 = v["latency_ms_p50"] / 1000, v["latency_ms_p95"] / 1000
        lines.append(
            f"| {_model(r)} | {p50:.1f} s / {p95:.1f} s | {c['llm_calls']} | "
            f"{c['total_tokens']:,} | {cost} |"
        )
    lines += [
        "",
        "Runs: " + ", ".join(f"`{r['_name']}` ({r['created_at']})" for r in ranked) + ".",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - thin CLI
    parser = argparse.ArgumentParser(description="Compare eval report JSON files")
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    text = render([_load(p) for p in args.reports])
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

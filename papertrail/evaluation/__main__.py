"""CLI: run the golden sets and (optionally) enforce the regression gate.

uv run python -m papertrail.evaluation --split smoke
uv run python -m papertrail.evaluation --split full --name anthropic-full
uv run python -m papertrail.evaluation --split smoke --baseline evals/baselines/mock-smoke.json
uv run python -m papertrail.evaluation --split smoke \
    --write-baseline evals/baselines/mock-smoke.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from papertrail.evaluation.runner import check_regression, run_eval, write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PaperTrail evaluation")
    parser.add_argument("--split", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--out", default="evals/reports")
    parser.add_argument("--name", help="Report file name (default: <provider>-<split>)")
    parser.add_argument("--baseline", help="Fail if headline metrics drop vs this JSON file")
    parser.add_argument("--max-drop", type=float, default=0.05, help="Allowed drop (0.05 = 5 pts)")
    parser.add_argument("--write-baseline", help="Save this run's headline metrics as a baseline")
    args = parser.parse_args(argv)

    report = run_eval(args.split)
    name = args.name or f"{report.provider}-{args.split}"
    _, md_path = write_report(report, Path(args.out), name)
    print(f"Report: {md_path}")
    for metric, value in report.headline().items():
        print(f"  {metric:28s} {value:.3f}")

    if args.write_baseline:
        path = Path(args.write_baseline)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.headline(), indent=2) + "\n", encoding="utf-8")
        print(f"Baseline written: {path}")

    if args.baseline:
        problems = check_regression(
            report, json.loads(Path(args.baseline).read_text()), args.max_drop
        )
        if problems:
            print("REGRESSION GATE FAILED:", *problems, sep="\n  - ", file=sys.stderr)
            return 1
        print("Regression gate passed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

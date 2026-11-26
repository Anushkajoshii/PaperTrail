import json
from pathlib import Path

from papertrail.evaluation.__main__ import main
from papertrail.evaluation.runner import check_regression, run_eval

BASELINE = Path(__file__).parent.parent / "evals" / "baselines" / "mock-smoke.json"


def test_smoke_eval_matches_committed_mock_baseline():
    """The offline smoke eval is deterministic; any change in behaviour shows up here."""
    report = run_eval("smoke")
    assert report.provider == "mock"
    assert report.verdicts["n"] == 15 and report.verdicts["accusatory_rate"] == 0
    assert check_regression(report, json.loads(BASELINE.read_text()), max_drop=0.05) == []


def test_regression_gate_flags_drops_and_safety():
    report = run_eval("smoke")
    inflated = {k: v + 0.2 for k, v in report.headline().items()}
    problems = check_regression(report, inflated, max_drop=0.05)
    assert len(problems) == len(inflated) and "dropped from" in problems[0]
    report.verdicts["accusatory_rate"] = 0.1
    assert any("accusatory" in p for p in check_regression(report, {}, 0.05))


def test_injection_item_is_not_fooled():
    report = run_eval("smoke")
    assert "v035" not in {m["id"] for m in report.verdicts["mistakes"]}


def test_cli_writes_reports_and_enforces_gate(tmp_path, capsys):
    assert main(["--split", "smoke", "--out", str(tmp_path), "--baseline", str(BASELINE)]) == 0
    md = (tmp_path / "mock-smoke.md").read_text()
    assert "Offline mock run" in md and "Confusion matrix" in md
    assert json.loads((tmp_path / "mock-smoke.json").read_text())["split"] == "smoke"
    strict = tmp_path / "strict.json"
    strict.write_text(json.dumps({"verdicts.accuracy": 1.5}))
    assert main(["--split", "smoke", "--out", str(tmp_path), "--baseline", str(strict)]) == 1
    assert "REGRESSION GATE FAILED" in capsys.readouterr().err

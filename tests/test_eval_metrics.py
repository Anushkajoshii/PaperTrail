import pytest

from papertrail.evaluation.metrics import (
    accuracy,
    brier,
    confusion,
    expected_calibration_error,
    macro_f1,
    per_class,
    percentile,
    prf_from_counts,
    set_prf,
)

GOLD = ["a", "a", "b", "b", "c"]
PRED = ["a", "b", "b", "b", "a"]
LABELS = ["a", "b", "c"]


def test_accuracy_and_per_class():
    assert accuracy(GOLD, PRED) == pytest.approx(0.6)
    scores = per_class(GOLD, PRED, LABELS)
    assert scores["a"].precision == 0.5 and scores["a"].recall == 0.5
    assert scores["b"].precision == pytest.approx(0.667) and scores["b"].recall == 1.0
    assert scores["c"].f1 == 0.0 and scores["c"].support == 1
    assert macro_f1(scores) == pytest.approx((0.5 + 0.8 + 0.0) / 3, abs=1e-3)
    assert accuracy([], []) == 0.0


def test_confusion_rows_are_gold():
    assert confusion(GOLD, PRED, LABELS) == [[1, 1, 0], [0, 2, 0], [1, 0, 0]]


def test_calibration():
    # Perfectly calibrated: 80% confidence, right 4 times out of 5.
    assert expected_calibration_error([0.8] * 5, [True] * 4 + [False]) == pytest.approx(0.0)
    # Over-confident: 90% confidence, always wrong.
    assert expected_calibration_error([0.9] * 4, [False] * 4) == pytest.approx(0.9)
    assert brier([1.0, 0.0], [True, False]) == 0.0 and brier([1.0], [False]) == 1.0


def test_percentile_and_set_metrics():
    assert percentile([10, 20, 30, 40, 100], 50) == 30
    assert percentile([10, 20, 30, 40, 100], 95) == 100
    assert set_prf({"x", "y"}, {"y", "z"}) == (1, 1, 1)
    assert prf_from_counts(1, 1, 1) == (0.5, 0.5, 0.5)
    assert prf_from_counts(0, 0, 0) == (0.0, 0.0, 0.0)

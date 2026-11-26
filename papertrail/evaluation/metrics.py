"""Evaluation metrics, written out in plain Python so each one is easy to explain.

* accuracy, per-class precision / recall / F1, macro-F1, confusion matrix
* expected calibration error (ECE) and Brier score: "when PaperTrail says 80% confident, is it
  right about 80% of the time?"
* percentiles for latency (p50 / p95)
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ClassScores:
    precision: float
    recall: float
    f1: float
    support: int


def accuracy(gold: Sequence[str], pred: Sequence[str]) -> float:
    if not gold:
        return 0.0
    return sum(g == p for g, p in zip(gold, pred, strict=True)) / len(gold)


def per_class(
    gold: Sequence[str], pred: Sequence[str], labels: Sequence[str]
) -> dict[str, ClassScores]:
    out = {}
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, pred, strict=True))
        fp = sum(g != label and p == label for g, p in zip(gold, pred, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, pred, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        out[label] = ClassScores(round(precision, 3), round(recall, 3), round(f1, 3), tp + fn)
    return out


def macro_f1(scores: dict[str, ClassScores]) -> float:
    present = [s.f1 for s in scores.values() if s.support > 0]
    return round(sum(present) / len(present), 3) if present else 0.0


def confusion(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str]) -> list[list[int]]:
    """Rows are gold labels, columns are predicted labels (in ``labels`` order)."""
    counts = Counter(zip(gold, pred, strict=True))
    return [[counts[(g, p)] for p in labels] for g in labels]


def expected_calibration_error(
    confidences: Sequence[float], correct: Sequence[bool], bins: int = 5
) -> float:
    """Weighted gap between average confidence and accuracy, across equal-width bins."""
    if not confidences:
        return 0.0
    n = len(confidences)
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(confidences) if lo <= c < hi or (b == bins - 1 and c == 1)]
        if not idx:
            continue
        avg_conf = sum(confidences[i] for i in idx) / len(idx)
        acc = sum(correct[i] for i in idx) / len(idx)
        total += len(idx) / n * abs(avg_conf - acc)
    return round(total, 3)


def brier(confidences: Sequence[float], correct: Sequence[bool]) -> float:
    if not confidences:
        return 0.0
    return round(
        sum((c - float(k)) ** 2 for c, k in zip(confidences, correct, strict=True))
        / len(confidences),
        3,
    )


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile (q in 0..100)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return round(ordered[rank - 1], 1)


def set_prf(gold: set[str], pred: set[str]) -> tuple[int, int, int]:
    """(true positives, false positives, false negatives) for set-valued predictions."""
    return len(gold & pred), len(pred - gold), len(gold - pred)


def prf_from_counts(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 3), round(r, 3), round(f, 3)

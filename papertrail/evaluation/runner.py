"""Run the golden sets through PaperTrail and score the results.

Three suites:
* **verdicts**: the judge on fixed evidence (accuracy, macro-F1, calibration, stance
  accuracy, citation validity, safety checks).
* **extraction**: claim extraction on transcripts (recall, type accuracy, precision).
* **rulebook**: deterministic red-flag rules (per-kind and micro precision/recall/F1).

A run uses whatever LLM provider is configured (mock by default), and the report always says
which one, so offline numbers are never mistaken for real-model numbers.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from papertrail.agent.extract import extract_claims
from papertrail.agent.judge import (
    JUDGE_PROMPT_VERSION,
    EvidenceCandidate,
    judge_claim,
)
from papertrail.agent.prompts import EXTRACT_PROMPT_VERSION
from papertrail.config import get_settings
from papertrail.evaluation import metrics as M
from papertrail.evaluation.golden import (
    ExtractionItem,
    RulebookItem,
    Split,
    VerdictItem,
    load_extraction,
    load_rulebook,
    load_verdicts,
)
from papertrail.llm import Provider, Purpose, UsageLog, get_provider, model_for
from papertrail.models import (
    Claim,
    RedFlagKind,
    RegistrationStatus,
    SebiRegistration,
    SourceQuality,
    VerdictLabel,
)
from papertrail.rulebook.concerns import ACCUSATORY
from papertrail.rulebook.rules import apply_rules
from papertrail.tools.source_quality import profile_for_type, recency_score, relevance_score

EVAL_DATE = date(2026, 11, 26)  # fixed "today" so recency scores are reproducible
LABELS = [v.value for v in VerdictLabel]


# ------------------------------------------------------------------------------------------
# Verdicts
# ------------------------------------------------------------------------------------------


def _candidates(item: VerdictItem, claim: Claim) -> list[EvidenceCandidate]:
    out = []
    for e in item.evidence:
        profile = profile_for_type(e.source_type)
        quality = SourceQuality(
            reliability=profile.reliability,
            recency=recency_score(e.published_at, claim.claim_type, EVAL_DATE),
            relevance=relevance_score(claim, e.snippet),
        )
        out.append(
            EvidenceCandidate(
                id=e.id,
                claim_id=claim.id,
                url=e.url,
                title=e.title,
                published_at=e.published_at,
                source_type=e.source_type,
                snippet=e.snippet,
                quality=quality,
                quality_labels={"reliability": profile.label},
            )
        )
    return out


@dataclass
class VerdictCase:
    id: str
    language: str
    gold: str
    pred: str
    confidence: float
    correct: bool
    stance_hits: int
    stance_total: int
    citations_valid: bool | None
    accusatory: bool
    latency_ms: float
    error: str | None = None


def run_verdicts(
    items: list[VerdictItem], provider: Provider, usage: UsageLog
) -> list[VerdictCase]:
    cases = []
    for item in items:
        claim = Claim(
            id=f"clm_{item.id}",
            text=item.claim.text,
            quote=item.claim.quote,
            claim_type=item.claim.claim_type,
            tickers=item.claim.tickers,
            language=item.language,
        )
        registration = (
            SebiRegistration(**item.registration.model_dump())
            if item.registration
            else SebiRegistration(status=RegistrationStatus.NOT_FOUND)
        )
        started = time.perf_counter()
        result = judge_claim(
            claim,
            _candidates(item, claim),
            provider=provider,
            registration=registration,
            today=EVAL_DATE,
            usage_log=usage,
        )
        latency = (time.perf_counter() - started) * 1000
        v = result.verdict
        predicted = {e.id: e.stance.value for e in result.evidence}
        hits = sum(
            predicted.get(eid, "irrelevant") == gold for eid, gold in item.gold_stances.items()
        )
        cited = (
            v.supporting_evidence_ids
            if v.label is VerdictLabel.SUPPORTED
            else v.contradicting_evidence_ids
            if v.label is VerdictLabel.CONTRADICTED
            else None
        )
        want = "supports" if v.label is VerdictLabel.SUPPORTED else "contradicts"
        citations_valid = (
            None if cited is None else all(item.gold_stances.get(i) == want for i in cited)
        )
        text = " ".join([v.explanation.summary, *v.explanation.reasoning])
        cases.append(
            VerdictCase(
                id=item.id,
                language=item.language.value,
                gold=item.gold_label.value,
                pred=v.label.value,
                confidence=v.confidence,
                correct=v.label is item.gold_label,
                stance_hits=hits,
                stance_total=len(item.gold_stances),
                citations_valid=citations_valid,
                accusatory=bool(ACCUSATORY.search(text)),
                latency_ms=round(latency, 1),
                error=result.error,
            )
        )
    return cases


def score_verdicts(cases: list[VerdictCase]) -> dict:
    gold, pred = [c.gold for c in cases], [c.pred for c in cases]
    classes = M.per_class(gold, pred, LABELS)
    by_lang: dict[str, list[VerdictCase]] = {}
    for c in cases:
        by_lang.setdefault(c.language, []).append(c)
    cited = [c.citations_valid for c in cases if c.citations_valid is not None]
    stance_total = sum(c.stance_total for c in cases)
    return {
        "n": len(cases),
        "accuracy": round(M.accuracy(gold, pred), 3),
        "macro_f1": M.macro_f1(classes),
        "per_class": {k: asdict(v) for k, v in classes.items()},
        "confusion": {"labels": LABELS, "matrix": M.confusion(gold, pred, LABELS)},
        "by_language": {
            k: round(M.accuracy([c.gold for c in v], [c.pred for c in v]), 3)
            for k, v in sorted(by_lang.items())
        },
        "ece": M.expected_calibration_error(
            [c.confidence for c in cases], [c.correct for c in cases]
        ),
        "brier": M.brier([c.confidence for c in cases], [c.correct for c in cases]),
        "stance_accuracy": round(sum(c.stance_hits for c in cases) / stance_total, 3)
        if stance_total
        else 0.0,
        "citation_validity": round(sum(cited) / len(cited), 3) if cited else 0.0,
        "accusatory_rate": round(sum(c.accusatory for c in cases) / len(cases), 3)
        if cases
        else 0.0,
        "errors": sum(c.error is not None for c in cases),
        "latency_ms_p50": M.percentile([c.latency_ms for c in cases], 50),
        "latency_ms_p95": M.percentile([c.latency_ms for c in cases], 95),
        "mistakes": [
            {"id": c.id, "gold": c.gold, "pred": c.pred, "confidence": c.confidence}
            for c in cases
            if not c.correct
        ],
    }


# ------------------------------------------------------------------------------------------
# Extraction
# ------------------------------------------------------------------------------------------


def run_extraction(items: list[ExtractionItem], provider: Provider, usage: UsageLog) -> dict:
    gold_total = matched = typed = extracted_total = false_pos = forbidden = 0
    misses: list[str] = []
    for item in items:
        result = extract_claims(item.text, provider=provider, language_hint=item.language)
        usage.calls.extend(result.usage.calls)
        quotes = [(c.quote.lower(), c.claim_type) for c in result.claims]
        extracted_total += len(quotes)
        used: set[int] = set()
        for g in item.claims:
            gold_total += 1
            hit = next((i for i, (q, _) in enumerate(quotes) if g.anchor.lower() in q), None)
            if hit is None:
                misses.append(f"{item.id}: {g.anchor}")
                continue
            matched += 1
            used.add(hit)
            if quotes[hit][1] is g.claim_type:
                typed += 1
        for i, (q, _) in enumerate(quotes):
            if i in used:
                continue
            if any(g.anchor.lower() in q for g in item.claims):
                continue  # a second claim from the same gold sentence is not a false positive
            false_pos += 1
            if any(n.lower() in q for n in item.not_claims):
                forbidden += 1
    precision = (extracted_total - false_pos) / extracted_total if extracted_total else 0.0
    return {
        "transcripts": len(items),
        "gold_claims": gold_total,
        "recall": round(matched / gold_total, 3) if gold_total else 0.0,
        "recall_strict": round(typed / gold_total, 3) if gold_total else 0.0,
        "type_accuracy": round(typed / matched, 3) if matched else 0.0,
        "precision": round(precision, 3),
        "forbidden_extractions": forbidden,
        "misses": misses,
    }


# ------------------------------------------------------------------------------------------
# Rulebook
# ------------------------------------------------------------------------------------------


def run_rulebook(items: list[RulebookItem]) -> dict:
    kinds = sorted({k for i in items for k in i.expect}, key=lambda k: k.value)
    counts = {k: [0, 0, 0] for k in RedFlagKind}
    total = [0, 0, 0]
    errors = []
    for item in items:
        reg = SebiRegistration(
            status=RegistrationStatus.REGISTERED_RA
            if item.registered
            else RegistrationStatus.NOT_FOUND
        )
        predicted = {f.kind for f in apply_rules(item.text, [], reg).flags}
        expected = set(item.expect)
        for k in RedFlagKind:
            tp, fp, fn = M.set_prf({k} & expected, {k} & predicted)
            counts[k][0] += tp
            counts[k][1] += fp
            counts[k][2] += fn
        tp, fp, fn = M.set_prf(expected, predicted)
        total = [total[0] + tp, total[1] + fp, total[2] + fn]
        if expected != predicted:
            errors.append(
                {
                    "id": item.id,
                    "expected": sorted(k.value for k in expected),
                    "predicted": sorted(k.value for k in predicted),
                    "note": item.note,
                }
            )
    p, r, f = M.prf_from_counts(*total)
    return {
        "sentences": len(items),
        "micro_precision": p,
        "micro_recall": r,
        "micro_f1": f,
        "per_kind": {
            k.value: dict(
                zip(("precision", "recall", "f1"), M.prf_from_counts(*counts[k]), strict=True)
            )
            for k in kinds
        },
        "errors": errors,
    }


# ------------------------------------------------------------------------------------------
# Report and regression gate
# ------------------------------------------------------------------------------------------

GATED = {
    "verdicts.accuracy": ("verdicts", "accuracy"),
    "verdicts.macro_f1": ("verdicts", "macro_f1"),
    "verdicts.stance_accuracy": ("verdicts", "stance_accuracy"),
    "extraction.recall_strict": ("extraction", "recall_strict"),
    "rulebook.micro_f1": ("rulebook", "micro_f1"),
}


@dataclass
class EvalReport:
    split: str
    provider: str
    models: dict[str, str]
    prompt_versions: dict[str, str]
    created_at: str
    verdicts: dict
    extraction: dict
    rulebook: dict
    cost: dict = field(default_factory=dict)

    def headline(self) -> dict[str, float]:
        return {name: getattr(self, a)[b] for name, (a, b) in GATED.items()}

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


def run_eval(split: Split = "smoke", provider: Provider | None = None) -> EvalReport:
    settings = get_settings()
    provider = provider or get_provider(settings)
    usage = UsageLog()
    verdict_items = load_verdicts(split)
    verdicts = score_verdicts(run_verdicts(verdict_items, provider, usage))
    extraction = run_extraction(load_extraction(split), provider, usage)
    rulebook = run_rulebook(load_rulebook(split))
    models = (
        {"extract": "mock", "judge": "mock"}
        if provider.name == "mock"
        else {p.value: model_for(p, settings) for p in Purpose}
    )
    return EvalReport(
        split=split,
        provider=provider.name,
        models=models,
        prompt_versions={"extract": EXTRACT_PROMPT_VERSION, "judge": JUDGE_PROMPT_VERSION},
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        verdicts=verdicts,
        extraction=extraction,
        rulebook=rulebook,
        cost={
            "llm_calls": len(usage.calls),
            "total_tokens": usage.total_tokens,
            "total_usd": usage.total_cost_usd,
            "usd_per_verdict": round(usage.total_cost_usd / max(1, len(verdict_items)), 5),
        },
    )


def check_regression(report: EvalReport, baseline: dict, max_drop: float = 0.05) -> list[str]:
    """Problems that should fail the build: metric drops beyond max_drop, or safety failures."""
    problems = []
    for name, value in report.headline().items():
        base = baseline.get(name)
        if base is not None and value < base - max_drop - 1e-9:
            problems.append(
                f"{name} dropped from {base:.3f} to {value:.3f} (allowed {max_drop:.2f})"
            )
    if report.verdicts["accusatory_rate"] > 0:
        problems.append("A verdict explanation used accusatory wording")
    return problems


def write_report(report: EvalReport, out_dir: Path, name: str) -> tuple[Path, Path]:
    from papertrail.evaluation.report import render_markdown

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{name}.json"
    md_path = out_dir / f"{name}.md"
    json_path.write_text(report.to_json() + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path

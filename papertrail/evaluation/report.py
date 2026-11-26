"""Render an EvalReport as Markdown (for the README results table and PR comments)."""

from __future__ import annotations

from papertrail.evaluation.runner import EvalReport


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def render_markdown(r: EvalReport) -> str:
    v, x, b = r.verdicts, r.extraction, r.rulebook
    mock = r.provider == "mock"
    lines = [
        f"# PaperTrail eval report: {r.split} split, provider `{r.provider}`",
        "",
        f"Generated {r.created_at} · models: extract `{r.models['extract']}`, judge "
        f"`{r.models['judge']}` · prompts: "
        + ", ".join(f"{k}={ver}" for k, ver in r.prompt_versions.items()),
        "",
    ]
    if mock:
        lines += [
            "> **Offline mock run.** These numbers measure the rule-based mock and the code "
            "around it. They are a regression baseline, **not** the accuracy of a real AI model.",
            "",
        ]
    lines += [
        "## Headline",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Verdict accuracy ({v['n']} claims) | {_pct(v['accuracy'])} |",
        f"| Verdict macro-F1 | {v['macro_f1']:.3f} |",
        f"| Evidence stance accuracy | {_pct(v['stance_accuracy'])} |",
        f"| Citation validity (supported/contradicted) | {_pct(v['citation_validity'])} |",
        f"| Calibration error (ECE, lower is better) | {v['ece']:.3f} |",
        f"| Claim-extraction recall ({x['gold_claims']} claims) | {_pct(x['recall'])} "
        f"(with correct type: {_pct(x['recall_strict'])}) |",
        f"| Claim-extraction precision | {_pct(x['precision'])} |",
        f"| Rulebook flags micro-F1 ({b['sentences']} sentences) | {b['micro_f1']:.3f} |",
        f"| Accusatory wording in explanations | {_pct(v['accusatory_rate'])} |",
        f"| Judge latency p50 / p95 | {v['latency_ms_p50']:.0f} ms / "
        f"{v['latency_ms_p95']:.0f} ms |",
        f"| Cost per verdict | ${r.cost['usd_per_verdict']:.5f} |",
        "",
        "## Verdicts by label",
        "",
        "| Label | Precision | Recall | F1 | Support |",
        "|---|---|---|---|---|",
    ]
    for label, s in v["per_class"].items():
        lines.append(
            f"| {label} | {s['precision']:.2f} | {s['recall']:.2f} | {s['f1']:.2f} | "
            f"{s['support']} |"
        )
    labels = v["confusion"]["labels"]
    lines += [
        "",
        "## Confusion matrix (rows = correct label, columns = predicted)",
        "",
        "| | " + " | ".join(labels) + " |",
        "|---" * (len(labels) + 1) + "|",
    ]
    for label, row in zip(labels, v["confusion"]["matrix"], strict=True):
        lines.append(f"| **{label}** | " + " | ".join(str(n) for n in row) + " |")
    lines += ["", "## Accuracy by language", "", "| Language | Accuracy |", "|---|---|"]
    lines += [f"| {k} | {_pct(a)} |" for k, a in v["by_language"].items()]
    lines += [
        "",
        "## Rulebook flags by kind",
        "",
        "| Kind | Precision | Recall | F1 |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {k} | {s['precision']:.2f} | {s['recall']:.2f} | {s['f1']:.2f} |"
        for k, s in b["per_kind"].items()
    ]
    lines += ["", "## Where it went wrong", ""]
    if v["mistakes"]:
        lines += [
            f"- Verdict `{m['id']}`: expected **{m['gold']}**, got **{m['pred']}** "
            f"(confidence {m['confidence']:.2f})"
            for m in v["mistakes"]
        ]
    lines += [f"- Extraction missed: {m}" for m in x["misses"]]
    lines += [
        f"- Rulebook `{e['id']}`: expected {e['expected']}, got {e['predicted']}"
        + (f" ({e['note']})" if e.get("note") else "")
        for e in b["errors"]
    ]
    if not (v["mistakes"] or x["misses"] or b["errors"]):
        lines.append("- Nothing: every item matched.")
    lines.append("")
    return "\n".join(lines)

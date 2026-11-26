# ADR-012: Evaluation design: fixed-evidence judge evals, honest baselines, a CI gate

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

The original plan asks for measured results (verdict accuracy, citation faithfulness, cost per
check) and a smoke eval on every PR that fails the build if accuracy drops by more than 5 points.
Two difficulties: real search results change over time, which makes end-to-end numbers
irreproducible, and CI has no LLM credentials.

## Decision

- **Test the judge on fixed evidence.** Each verdict item ships its own passages, so the judge's
  reasoning is measured reproducibly and separately from search quality. Search and retrieval
  get their own end-to-end evals later.
- **Three suites, one runner:** verdicts, extraction and rulebook, scored with standard metrics
  (accuracy, macro-F1, ECE, precision/recall), all implemented in plain Python
  (`papertrail/evaluation/metrics.py`).
- **Synthetic v1, real v2.** v1 uses fictional companies on `.eval.test` URLs, which avoids any
  claim about real people. v2 adds real claims from public SEBI orders and a second annotator.
- **Two kinds of run, always labelled:**
  - The offline mock run is a deterministic **regression baseline**, gated in CI (>5-point drop
    fails).
  - Real-model runs (Anthropic now, Bedrock after Part 10) are manual, so they never spend money
    by surprise. They produce the published results table.
- **Safety is gated too:** any accusatory wording in an explanation fails the build.

## Consequences

- ✅ Every PR proves it didn't break extraction, judging logic or the rulebook.
- ✅ Reports name the provider, models and prompt versions, so mock numbers can't be passed off as
  model accuracy.
- ➖ The mock gate cannot catch prompt regressions that only show with a real model. The manual
  real-model workflow covers that, and moves into CI once Bedrock via OIDC exists (Part 10).

## In plain English

We keep a fixed set of practice questions with known answers. Every change to the code is tested
against them automatically, and real AI accuracy is measured on the same questions when we choose
to run it.

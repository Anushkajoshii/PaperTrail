# ADR-019: Golden set v2 and a model comparison, without tuning on the test set

- **Status:** Accepted
- **Date:** 2026-11-28

## Context

The first golden set (40 verdicts, 10 transcripts) was too small to tell models apart or to
say anything per language. PaperTrail runs on Groq's free tier, so the choice of model should
rest on measurement, not reputation. Free-tier limits (about 1,000 requests a day per model,
shared with the live site) make each full run slow.

## Decision

- **Golden set v2:** 95 verdicts (24/24/23/24 across the four labels; 59 English, 23 Hinglish,
  13 Hindi), 20 transcripts with 55 gold claims, and 52 rulebook sentences, including
  negations and look-alikes. All cases are written for the set. None quotes real people from
  SEBI orders.
- **Same set, one table:** `papertrail.evaluation.compare` builds
  `evals/reports/model-comparison.md` from saved report JSON files, and refuses runs made on
  different golden sets.
- **No tuning on the test set.** The judge prompt was not changed after seeing v2 errors. The
  rulebook was fixed using v2 sentences, so its score is reported as not held out.
- **Fail visibly.** Requests the free tier can never serve ("request too large") fail at
  once. One failed transcript counts as missed claims instead of crashing the run.

## Results (27 Nov 2026)

| Model | Verdict accuracy | Macro-F1 | Misleading F1 | Extraction recall |
|---|---|---|---|---|
| gpt-oss-120b | 83% | 0.80 | 0.47 | 98% |
| gpt-oss-20b | 79% | 0.76 | 0.45 | 100% |
| rule-based mock | 50% | 0.46 | 0.41 | 86% |

gpt-oss-120b stays the judge and gpt-oss-20b the extractor. Almost all errors are on
"misleading": technically true claims that are missing context, called "supported", and
guaranteed-return promises called "contradicted".

A `qwen/qwen3.8-27b` run was started but ran out of the free daily quota (65 of 95 verdicts
failed), so it is left out instead of being reported as a poor score.

## Consequences

- The weakness on "misleading" is documented in the limitations and is the next thing to
  improve, with a new held-out set to measure it.
- The set is small and has one annotator, so differences of a few points are not meaningful.

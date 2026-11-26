# ADR-005: A small model extracts, a stronger model judges

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

Extraction (listing claims) is a high-volume pattern-matching task. Judging (weighing evidence
and explaining a verdict) needs more careful reasoning but runs on fewer, shorter inputs. Using
the strongest model for everything wastes money. Using the smallest for everything risks wrong
verdicts.

## Decision

- Each LLM call declares its `Purpose` (`extract` or `judge`). The provider picks the model and
  effort for that purpose.
- Defaults: **Claude Haiku 5.5** (effort `low`) for extraction, **Claude Opus 5.5** (effort `medium`)
  for judging. On Bedrock the same models use the `anthropic.` prefix.
- Both can be overridden with `PAPERTRAIL_EXTRACT_MODEL` / `PAPERTRAIL_JUDGE_MODEL`, which is how
  the eval report compares setups, e.g. "small model only" vs "small extract + strong judge"
  (Part 13).
- Every call records tokens, latency and an estimated cost, which add up to **cost per check**.
- A refusal (`stop_reason: "refusal"`) or a truncated answer raises a clear error. The agent
  (Part 5) turns that into a "not verifiable" result for the affected claim rather than guessing.
  Server-side model fallbacks are not enabled for now. They are a beta feature, unavailable on
  Bedrock, and refusals are unlikely for this content.

## Consequences

- ✅ Cost and quality can be traded off with configuration alone, and measured.
- ✅ The cost/accuracy table in the README comes straight from this design.
- ➖ Two models means two sets of behaviour to evaluate. The eval suite covers both.

## In plain English

We use a cheap, fast AI to find the claims and a smarter AI to decide whether they hold up, much
like a junior researcher and a senior editor. Either can be swapped with a setting.

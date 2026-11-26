# How PaperTrail is evaluated

Accuracy claims are only worth something if they are measured honestly. This page explains the
golden sets, the labelling rubric, every metric, and how to run evals.

## Quick start

```bash
make eval-smoke     # 15 claims, offline, with the regression gate (what CI runs on every PR)
make eval           # all 40 claims with the configured LLM provider
```

Reports are written to `evals/reports/<provider>-<split>.md` (and `.json`). Every report says
which provider, models and prompt versions produced it.

> **Offline (mock) numbers are not model accuracy.** With `PAPERTRAIL_LLM_PROVIDER=mock`, verdicts
> come from simple number-matching rules. That run is a *regression baseline* that catches code
> changes that break behaviour. Real-model results come from running the same sets with
> `anthropic` or `bedrock`.

## The golden sets (`evals/golden/`)

| Set | Size | What it tests |
|---|---|---|
| `verdicts.yaml` | 40 claims (15 in the smoke split) | The judge, given a **fixed** set of evidence passages, separately from search quality |
| `extraction.yaml` | 10 transcripts, 28 gold claims | Finding the checkable claims, with the right type, and nothing else |
| `rulebook.yaml` | 32 sentences | The deterministic SEBI red-flag rules, including look-alike negatives |

Coverage: all four verdict labels; English, Hinglish and Hindi; conflicting and irrelevant
sources; a social post repeating a claim; a prompt-injection passage; private claims; future
predictions; registered and not-found credentials.

**Honesty notes.** v1 is synthetic: companies are fictional and evidence uses `.eval.test` URLs,
so nothing describes a real company or person. Labels were assigned by one annotator using the
rubric below. Golden set v2 (Part 13) adds real claims drawn from public SEBI orders, a second
annotator and an agreement score.

## Labelling rubric

Label each claim **using only the evidence given**:

| Label | Use when |
|---|---|
| supported | Reliable evidence directly confirms the specific facts (numbers, dates, names). |
| contradicted | Reliable evidence directly states something incompatible. |
| misleading | Partly or technically true, but missing context changes the meaning: a cherry-picked period, losses or fees left out, a segment presented as the whole market, or guaranteed returns presented as normal. |
| not_verifiable | Not enough reliable evidence, private facts, opinions in blogs, or predictions about the future. |

Each evidence passage also gets a gold stance: `supports`, `contradicts`, `context` or
`irrelevant`.

## Metrics, in plain English

| Metric | What it means |
|---|---|
| Verdict accuracy | Share of claims where PaperTrail's verdict equals the gold label. |
| Macro-F1 | Average of per-label F1 scores, so rare labels count as much as common ones. |
| Confusion matrix | Which labels get mixed up with which, e.g. "misleading" judged as "supported". |
| Evidence stance accuracy | Share of passages given the right role (supports / contradicts / context / irrelevant). |
| Citation validity | For supported/contradicted verdicts: are all cited passages really the right kind? |
| Calibration error (ECE) | When PaperTrail says "80% confident", is it right about 80% of the time? Lower is better. |
| Extraction recall | Share of gold claims found. "Strict" also requires the right claim type. |
| Extraction precision | Share of extracted claims that are real gold claims. |
| Rulebook micro-F1 | How well the red-flag rules hit the expected flags without false alarms. |
| Accusatory wording rate | Must be 0%: explanations never call anyone a scammer, liar or fraud. |
| Latency p50 / p95 | Typical and slow-case time for the judge per claim. |
| Cost per verdict | Estimated LLM cost from token usage. |

## The regression gate

`evals/baselines/mock-smoke.json` stores the headline metrics of the offline smoke run. CI fails
a pull request if any of these drops by more than 5 points, or if any explanation uses accusatory
wording:

- verdict accuracy and macro-F1
- evidence stance accuracy
- strict extraction recall
- rulebook micro-F1

After a deliberate improvement, update the baseline:

```bash
uv run python -m papertrail.evaluation --split smoke --write-baseline evals/baselines/mock-smoke.json
```

## Real-model evals

- **Locally:** set `PAPERTRAIL_LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` in `.env`, then
  `make eval`.
- **In GitHub Actions:** add the `ANTHROPIC_API_KEY` repository secret, then run the manual
  **Eval (real model)** workflow. It never runs automatically, so it cannot spend money by
  surprise.

## Adding items

Add to the YAML files, keep URLs on `.eval.test`, write a one-line `why`, and run `make test`.
The loader rejects unknown labels, dangling evidence ids and anchors that are not in the text.

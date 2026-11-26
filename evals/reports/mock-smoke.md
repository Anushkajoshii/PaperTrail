# PaperTrail eval report: smoke split, provider `mock`

Generated 2026-11-26T18:22:42+00:00 · models: extract `mock`, judge `mock` · prompts: extract=extract-v1, judge=judge-v1

> **Offline mock run.** These numbers measure the rule-based mock and the code around it. They are a regression baseline, **not** the accuracy of a real AI model.

## Headline

| Metric | Value |
|---|---|
| Verdict accuracy (15 claims) | 80.0% |
| Verdict macro-F1 | 0.789 |
| Evidence stance accuracy | 64.3% |
| Citation validity (supported/contradicted) | 71.4% |
| Calibration error (ECE, lower is better) | 0.144 |
| Claim-extraction recall (6 claims) | 100.0% (with correct type: 100.0%) |
| Claim-extraction precision | 100.0% |
| Rulebook flags micro-F1 (9 sentences) | 0.900 |
| Accusatory wording in explanations | 0.0% |
| Judge latency p50 / p95 | 0 ms / 0 ms |
| Cost per verdict | $0.00000 |

## Verdicts by label

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| supported | 0.80 | 1.00 | 0.89 | 4 |
| contradicted | 1.00 | 0.50 | 0.67 | 4 |
| misleading | 1.00 | 0.67 | 0.80 | 3 |
| not_verifiable | 0.67 | 1.00 | 0.80 | 4 |

## Confusion matrix (rows = correct label, columns = predicted)

| | supported | contradicted | misleading | not_verifiable |
|---|---|---|---|---|
| **supported** | 4 | 0 | 0 | 0 |
| **contradicted** | 0 | 2 | 0 | 2 |
| **misleading** | 1 | 0 | 2 | 0 |
| **not_verifiable** | 0 | 0 | 0 | 4 |

## Accuracy by language

| Language | Accuracy |
|---|---|
| en | 70.0% |
| hinglish | 100.0% |

## Rulebook flags by kind

| Kind | Precision | Recall | F1 |
|---|---|---|---|
| guaranteed_returns | 1.00 | 1.00 | 1.00 |
| live_price_education | 1.00 | 1.00 | 1.00 |
| misleading_performance | 0.50 | 1.00 | 0.67 |
| pressure_tactics | 1.00 | 1.00 | 1.00 |
| tip_group_solicitation | 1.00 | 0.50 | 0.67 |
| unconfirmed_registration_claim | 1.00 | 1.00 | 1.00 |
| unregistered_advice | 1.00 | 1.00 | 1.00 |

## Where it went wrong

- Verdict `v013`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v016`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v022`: expected **misleading**, got **supported** (confidence 0.82)
- Rulebook `r01`: expected ['guaranteed_returns', 'tip_group_solicitation'], got ['guaranteed_returns', 'misleading_performance']

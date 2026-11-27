# PaperTrail eval report: full split, provider `groq`

Generated 2026-11-27T15:29:46+00:00 · models: extract `openai/gpt-oss-20b`, judge `openai/gpt-oss-20b` · prompts: extract=extract-v1, judge=judge-v1

## Headline

| Metric | Value |
|---|---|
| Verdict accuracy (95 claims) | 78.9% |
| Verdict macro-F1 | 0.759 |
| Evidence stance accuracy | 67.7% |
| Citation validity (supported/contradicted) | 66.7% |
| Calibration error (ECE, lower is better) | 0.180 |
| Claim-extraction recall (55 claims) | 100.0% (with correct type: 87.3%) |
| Claim-extraction precision | 96.4% |
| Rulebook flags micro-F1 (52 sentences) | 1.000 |
| Accusatory wording in explanations | 0.0% |
| Judge latency p50 / p95 | 4472 ms / 11787 ms |
| Cost per verdict | $0.00000 |

## Verdicts by label

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| supported | 0.74 | 0.96 | 0.84 | 24 |
| contradicted | 0.69 | 1.00 | 0.81 | 24 |
| misleading | 0.88 | 0.30 | 0.45 | 23 |
| not_verifiable | 1.00 | 0.88 | 0.93 | 24 |

## Confusion matrix (rows = correct label, columns = predicted)

| | supported | contradicted | misleading | not_verifiable |
|---|---|---|---|---|
| **supported** | 23 | 1 | 0 | 0 |
| **contradicted** | 0 | 24 | 0 | 0 |
| **misleading** | 8 | 8 | 7 | 0 |
| **not_verifiable** | 0 | 2 | 1 | 21 |

## Accuracy by language

| Language | Accuracy |
|---|---|
| en | 81.4% |
| hi | 76.9% |
| hinglish | 73.9% |

## Rulebook flags by kind

| Kind | Precision | Recall | F1 |
|---|---|---|---|
| guaranteed_returns | 1.00 | 1.00 | 1.00 |
| live_price_education | 1.00 | 1.00 | 1.00 |
| misleading_performance | 1.00 | 1.00 | 1.00 |
| pressure_tactics | 1.00 | 1.00 | 1.00 |
| tip_group_solicitation | 1.00 | 1.00 | 1.00 |
| unconfirmed_registration_claim | 1.00 | 1.00 | 1.00 |
| unregistered_advice | 1.00 | 1.00 | 1.00 |

## Where it went wrong

- Verdict `v021`: expected **misleading**, got **contradicted** (confidence 0.82)
- Verdict `v022`: expected **misleading**, got **supported** (confidence 0.82)
- Verdict `v024`: expected **misleading**, got **contradicted** (confidence 0.71)
- Verdict `v025`: expected **misleading**, got **contradicted** (confidence 0.84)
- Verdict `v027`: expected **misleading**, got **contradicted** (confidence 0.82)
- Verdict `v028`: expected **misleading**, got **supported** (confidence 0.76)
- Verdict `v032`: expected **not_verifiable**, got **contradicted** (confidence 0.72)
- Verdict `v046`: expected **supported**, got **contradicted** (confidence 0.73)
- Verdict `v069`: expected **misleading**, got **supported** (confidence 0.85)
- Verdict `v070`: expected **misleading**, got **contradicted** (confidence 0.82)
- Verdict `v071`: expected **misleading**, got **contradicted** (confidence 0.82)
- Verdict `v072`: expected **misleading**, got **supported** (confidence 0.76)
- Verdict `v074`: expected **misleading**, got **supported** (confidence 0.73)
- Verdict `v077`: expected **misleading**, got **supported** (confidence 0.81)
- Verdict `v078`: expected **misleading**, got **contradicted** (confidence 0.82)
- Verdict `v079`: expected **misleading**, got **contradicted** (confidence 0.72)
- Verdict `v081`: expected **misleading**, got **supported** (confidence 0.77)
- Verdict `v082`: expected **misleading**, got **supported** (confidence 0.78)
- Verdict `v089`: expected **not_verifiable**, got **misleading** (confidence 0.69)
- Verdict `v095`: expected **not_verifiable**, got **contradicted** (confidence 0.82)

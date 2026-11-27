# PaperTrail eval report: full split, provider `groq`

Generated 2026-11-27T13:54:31+00:00 · models: extract `openai/gpt-oss-120b`, judge `openai/gpt-oss-120b` · prompts: extract=extract-v1, judge=judge-v1

## Headline

| Metric | Value |
|---|---|
| Verdict accuracy (95 claims) | 83.2% |
| Verdict macro-F1 | 0.795 |
| Evidence stance accuracy | 76.0% |
| Citation validity (supported/contradicted) | 70.3% |
| Calibration error (ECE, lower is better) | 0.241 |
| Claim-extraction recall (55 claims) | 98.2% (with correct type: 85.5%) |
| Claim-extraction precision | 94.6% |
| Rulebook flags micro-F1 (52 sentences) | 1.000 |
| Accusatory wording in explanations | 0.0% |
| Judge latency p50 / p95 | 5086 ms / 9650 ms |
| Cost per verdict | $0.00000 |

## Verdicts by label

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| supported | 0.73 | 1.00 | 0.84 | 24 |
| contradicted | 0.77 | 1.00 | 0.87 | 24 |
| misleading | 1.00 | 0.30 | 0.47 | 23 |
| not_verifiable | 1.00 | 1.00 | 1.00 | 24 |

## Confusion matrix (rows = correct label, columns = predicted)

| | supported | contradicted | misleading | not_verifiable |
|---|---|---|---|---|
| **supported** | 24 | 0 | 0 | 0 |
| **contradicted** | 0 | 24 | 0 | 0 |
| **misleading** | 9 | 7 | 7 | 0 |
| **not_verifiable** | 0 | 0 | 0 | 24 |

## Accuracy by language

| Language | Accuracy |
|---|---|
| en | 84.7% |
| hi | 84.6% |
| hinglish | 78.3% |

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
- Verdict `v069`: expected **misleading**, got **supported** (confidence 0.85)
- Verdict `v070`: expected **misleading**, got **contradicted** (confidence 0.82)
- Verdict `v071`: expected **misleading**, got **contradicted** (confidence 0.82)
- Verdict `v072`: expected **misleading**, got **supported** (confidence 0.76)
- Verdict `v074`: expected **misleading**, got **supported** (confidence 0.73)
- Verdict `v077`: expected **misleading**, got **supported** (confidence 0.81)
- Verdict `v078`: expected **misleading**, got **contradicted** (confidence 0.82)
- Verdict `v080`: expected **misleading**, got **supported** (confidence 0.84)
- Verdict `v081`: expected **misleading**, got **supported** (confidence 0.77)
- Verdict `v082`: expected **misleading**, got **supported** (confidence 0.78)
- Extraction missed: x17: debt-free

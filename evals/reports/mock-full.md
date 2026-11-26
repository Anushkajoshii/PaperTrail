# PaperTrail eval report: full split, provider `mock`

Generated 2026-11-26T18:22:41+00:00 · models: extract `mock`, judge `mock` · prompts: extract=extract-v1, judge=judge-v1

> **Offline mock run.** These numbers measure the rule-based mock and the code around it. They are a regression baseline, **not** the accuracy of a real AI model.

## Headline

| Metric | Value |
|---|---|
| Verdict accuracy (40 claims) | 62.5% |
| Verdict macro-F1 | 0.567 |
| Evidence stance accuracy | 57.5% |
| Citation validity (supported/contradicted) | 61.1% |
| Calibration error (ECE, lower is better) | 0.125 |
| Claim-extraction recall (28 claims) | 89.3% (with correct type: 60.7%) |
| Claim-extraction precision | 100.0% |
| Rulebook flags micro-F1 (32 sentences) | 0.909 |
| Accusatory wording in explanations | 0.0% |
| Judge latency p50 / p95 | 0 ms / 0 ms |
| Cost per verdict | $0.00000 |

## Verdicts by label

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| supported | 0.62 | 1.00 | 0.77 | 10 |
| contradicted | 1.00 | 0.20 | 0.33 | 10 |
| misleading | 1.00 | 0.33 | 0.50 | 9 |
| not_verifiable | 0.53 | 0.91 | 0.67 | 11 |

## Confusion matrix (rows = correct label, columns = predicted)

| | supported | contradicted | misleading | not_verifiable |
|---|---|---|---|---|
| **supported** | 10 | 0 | 0 | 0 |
| **contradicted** | 2 | 2 | 0 | 6 |
| **misleading** | 3 | 0 | 3 | 3 |
| **not_verifiable** | 1 | 0 | 0 | 10 |

## Accuracy by language

| Language | Accuracy |
|---|---|
| en | 51.9% |
| hi | 75.0% |
| hinglish | 88.9% |

## Rulebook flags by kind

| Kind | Precision | Recall | F1 |
|---|---|---|---|
| guaranteed_returns | 0.80 | 1.00 | 0.89 |
| live_price_education | 1.00 | 1.00 | 1.00 |
| misleading_performance | 0.75 | 1.00 | 0.86 |
| pressure_tactics | 0.80 | 1.00 | 0.89 |
| tip_group_solicitation | 1.00 | 0.67 | 0.80 |
| unconfirmed_registration_claim | 1.00 | 1.00 | 1.00 |
| unregistered_advice | 1.00 | 1.00 | 1.00 |

## Where it went wrong

- Verdict `v013`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v014`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v015`: expected **contradicted**, got **supported** (confidence 0.77)
- Verdict `v016`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v017`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v018`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v019`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v020`: expected **contradicted**, got **supported** (confidence 0.76)
- Verdict `v022`: expected **misleading**, got **supported** (confidence 0.82)
- Verdict `v023`: expected **misleading**, got **supported** (confidence 0.74)
- Verdict `v024`: expected **misleading**, got **not_verifiable** (confidence 0.40)
- Verdict `v026`: expected **misleading**, got **supported** (confidence 0.80)
- Verdict `v028`: expected **misleading**, got **not_verifiable** (confidence 0.40)
- Verdict `v029`: expected **misleading**, got **not_verifiable** (confidence 0.40)
- Verdict `v037`: expected **not_verifiable**, got **supported** (confidence 0.64)
- Extraction missed: x06: never had a losing year
- Extraction missed: x06: expense ratio is zero
- Extraction missed: x10: debt-free
- Rulebook `r01`: expected ['guaranteed_returns', 'tip_group_solicitation'], got ['guaranteed_returns', 'misleading_performance']
- Rulebook `r31`: expected [], got ['guaranteed_returns'] (negated guarantee: known false positive)
- Rulebook `r32`: expected [], got ['pressure_tactics'] (neutral 'hurry': known false positive)

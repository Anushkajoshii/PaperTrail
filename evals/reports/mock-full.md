# PaperTrail eval report: full split, provider `mock`

Generated 2026-11-27T13:43:16+00:00 · models: extract `mock`, judge `mock` · prompts: extract=extract-v1, judge=judge-v1

> **Offline mock run.** These numbers measure the rule-based mock and the code around it. They are a regression baseline, **not** the accuracy of a real AI model.

## Headline

| Metric | Value |
|---|---|
| Verdict accuracy (95 claims) | 49.5% |
| Verdict macro-F1 | 0.462 |
| Evidence stance accuracy | 44.8% |
| Citation validity (supported/contradicted) | 37.5% |
| Calibration error (ECE, lower is better) | 0.199 |
| Claim-extraction recall (55 claims) | 85.5% (with correct type: 50.9%) |
| Claim-extraction precision | 97.6% |
| Rulebook flags micro-F1 (52 sentences) | 1.000 |
| Accusatory wording in explanations | 0.0% |
| Judge latency p50 / p95 | 0 ms / 0 ms |
| Cost per verdict | $0.00000 |

## Verdicts by label

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| supported | 0.50 | 0.67 | 0.57 | 24 |
| contradicted | 0.31 | 0.21 | 0.25 | 24 |
| misleading | 1.00 | 0.26 | 0.41 | 23 |
| not_verifiable | 0.49 | 0.83 | 0.61 | 24 |

## Confusion matrix (rows = correct label, columns = predicted)

| | supported | contradicted | misleading | not_verifiable |
|---|---|---|---|---|
| **supported** | 16 | 6 | 0 | 2 |
| **contradicted** | 6 | 5 | 0 | 13 |
| **misleading** | 8 | 3 | 6 | 6 |
| **not_verifiable** | 2 | 2 | 0 | 20 |

## Accuracy by language

| Language | Accuracy |
|---|---|
| en | 42.4% |
| hi | 53.8% |
| hinglish | 65.2% |

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
- Verdict `v042`: expected **supported**, got **contradicted** (confidence 0.80)
- Verdict `v043`: expected **supported**, got **not_verifiable** (confidence 0.40)
- Verdict `v046`: expected **supported**, got **contradicted** (confidence 0.73)
- Verdict `v047`: expected **supported**, got **contradicted** (confidence 0.79)
- Verdict `v049`: expected **supported**, got **not_verifiable** (confidence 0.40)
- Verdict `v050`: expected **supported**, got **contradicted** (confidence 0.60)
- Verdict `v051`: expected **supported**, got **contradicted** (confidence 0.50)
- Verdict `v054`: expected **supported**, got **contradicted** (confidence 0.71)
- Verdict `v055`: expected **contradicted**, got **supported** (confidence 0.80)
- Verdict `v056`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v058`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v059`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v060`: expected **contradicted**, got **supported** (confidence 0.77)
- Verdict `v061`: expected **contradicted**, got **supported** (confidence 0.84)
- Verdict `v062`: expected **contradicted**, got **supported** (confidence 0.79)
- Verdict `v063`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v065`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v066`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v067`: expected **contradicted**, got **not_verifiable** (confidence 0.40)
- Verdict `v069`: expected **misleading**, got **supported** (confidence 0.85)
- Verdict `v072`: expected **misleading**, got **contradicted** (confidence 0.76)
- Verdict `v073`: expected **misleading**, got **contradicted** (confidence 0.77)
- Verdict `v074`: expected **misleading**, got **supported** (confidence 0.73)
- Verdict `v075`: expected **misleading**, got **not_verifiable** (confidence 0.40)
- Verdict `v076`: expected **misleading**, got **supported** (confidence 0.78)
- Verdict `v077`: expected **misleading**, got **not_verifiable** (confidence 0.40)
- Verdict `v079`: expected **misleading**, got **not_verifiable** (confidence 0.40)
- Verdict `v080`: expected **misleading**, got **supported** (confidence 0.84)
- Verdict `v081`: expected **misleading**, got **contradicted** (confidence 0.77)
- Verdict `v082`: expected **misleading**, got **supported** (confidence 0.78)
- Verdict `v089`: expected **not_verifiable**, got **contradicted** (confidence 0.80)
- Verdict `v093`: expected **not_verifiable**, got **supported** (confidence 0.84)
- Verdict `v095`: expected **not_verifiable**, got **contradicted** (confidence 0.80)
- Extraction missed: x06: never had a losing year
- Extraction missed: x06: expense ratio is zero
- Extraction missed: x10: debt-free
- Extraction missed: x12: ek bonus share
- Extraction missed: x13: कोई कर्ज़ नहीं
- Extraction missed: x13: 25 MTPA
- Extraction missed: x13: सेबी रजिस्टर्ड एडवाइज़र
- Extraction missed: x18: approval for two products

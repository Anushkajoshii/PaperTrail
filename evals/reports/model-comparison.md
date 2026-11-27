# Model comparison

Same golden set for every row: 95 verdicts judged on fixed evidence and 55 gold claims in 20 transcripts. Each row used one model for both extraction and judging. The `mock` row is the offline rule-based baseline, **not** an AI model.

## Verdicts

| Model | Accuracy | Macro-F1 | Calibration error (ECE, lower is better) | Brier | Evidence stance | Citation validity | Judge errors | Accusatory wording |
|---|---|---|---|---|---|---|---|---|
| groq: openai/gpt-oss-120b | 83% | 0.80 | 0.24 | 0.23 | 76% | 70% | 0 | 0% |
| groq: openai/gpt-oss-20b | 79% | 0.76 | 0.18 | 0.23 | 68% | 67% | 0 | 0% |
| mock: mock | 50% | 0.46 | 0.20 | 0.29 | 45% | 38% | 0 | 0% |

## F1 per verdict label

| Model | supported | contradicted | misleading | not_verifiable |
|---|---|---|---|---|
| groq: openai/gpt-oss-120b | 0.84 | 0.87 | 0.47 | 1.00 |
| groq: openai/gpt-oss-20b | 0.84 | 0.81 | 0.45 | 0.93 |
| mock: mock | 0.57 | 0.25 | 0.41 | 0.61 |

## Verdict accuracy by language

| Model | en | hi | hinglish |
|---|---|---|---|
| groq: openai/gpt-oss-120b | 85% | 85% | 78% |
| groq: openai/gpt-oss-20b | 81% | 77% | 74% |
| mock: mock | 42% | 54% | 65% |

## Claim extraction

| Model | Recall | Recall with correct type | Precision | Forbidden extractions |
|---|---|---|---|---|
| groq: openai/gpt-oss-20b | 100% | 87% | 96% | 0 |
| groq: openai/gpt-oss-120b | 98% | 86% | 95% | 0 |
| mock: mock | 86% | 51% | 98% | 1 |

## Speed and cost

| Model | Verdict time p50 / p95 | AI calls | Tokens | Cost |
|---|---|---|---|---|
| groq: openai/gpt-oss-120b | 5.1 s / 9.6 s | 107 | 126,356 | $0 (free tier) |
| groq: openai/gpt-oss-20b | 4.5 s / 11.8 s | 117 | 129,356 | $0 (free tier) |
| mock: mock | 0.0 s / 0.0 s | 107 | 73,745 | $0 (free tier) |

Runs: `groq-openai-gpt-oss-120b-full` (2026-11-27T13:54:31+00:00), `groq-openai-gpt-oss-20b-full` (2026-11-27T15:29:46+00:00), `mock-full` (2026-11-27T13:43:16+00:00).

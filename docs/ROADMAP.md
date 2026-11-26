# Roadmap and progress

PaperTrail is built in 14 parts. Each part is developed on its own branch, verified (tests,
lint, docs), merged through a pull request, and approved before the next part starts.

Legend: ✅ done · 🔄 in progress · ⬜ not started · ☁️ needs AWS (asks for approval first)

| # | Part | Branch | Status |
|---|---|---|---|
| 1 | Foundation: scaffold, docs, data models, CI | `part-1/scaffold` | ✅ |
| 2 | LLM layer (pluggable + mock) and claim extraction | `part-2/llm-claims` | ⬜ |
| 3 | Evidence tools: transcription, search, safe fetch, source quality | `part-3/evidence` | ⬜ |
| 4 | SEBI Rulebook Intelligence and registry lookup | `part-4/sebi` | ⬜ |
| 5 | LangGraph agent and explainable judge | `part-5/agent` | ⬜ |
| 6 | Golden set v1, eval runner, CI smoke-eval gate | `part-6/evals` | ⬜ |
| 7 | FastAPI, local worker, Docker Compose, API docs | `part-7/api` | ⬜ |
| 8 | Web app: landing, guided input, progress, results, rulebook, glossary | `part-8/web` | ⬜ |
| 9 | Downloadable source-cited report and shareable result | `part-9/report` | ⬜ |
| 10 | ☁️ AWS: Terraform, OIDC CI/CD deploy, budgets | `part-10/aws` | ⬜ |
| 11 | Langfuse tracing and cost per check | `part-11/tracing` | ⬜ |
| 12 | Claim Ledger, creator profile, red-flag timeline, creator comparison | `part-12/ledger` | ⬜ |
| 13 | Golden set v2 (90+ claims) and model comparison report | `part-13/eval-v2` | ⬜ |
| 14 | Polish: diagrams, demo GIF, tester fixes, MCP server (stretch) | `part-14/polish` | ⬜ |

## How each part maps to the original plan

| Original commit milestone | Part |
|---|---|
| scaffold repo with uv, ruff, pytest, pre-commit | 1 |
| README skeleton and ADR-001 uploads-not-scraping | 1 |
| Pydantic models for Claim, Evidence, Verdict | 1 |
| transcribe tool using Amazon Transcribe | 3 |
| claim extraction node with structured output, plus parsing tests | 2 |
| search and fetch tools with injection-safe text | 3 |
| SEBI registry loader and lookup tool | 4 |
| LangGraph agent with evidence loop and max-steps guard | 5 |
| judge node with verdict rubric and citations | 5 |
| golden set v1 (40 claims) and eval runner | 6 |
| FastAPI routes and local run with docker compose | 7 |
| Terraform for S3, DynamoDB, SQS, Lambdas, API Gateway | 10 |
| test, smoke eval and deploy via GitHub OIDC | 6 (eval gate), 10 (deploy) |
| React upload page and results view | 8 |
| Langfuse tracing and cost tracking | 11 |
| golden set v2 and model comparison report | 13 |
| Claim Ledger and daily EventBridge job | 12 |
| creator page with accountability score | 12 |
| fixes from 10 friend testers | 14 |
| architecture diagram, results table, demo GIF, limitations | 14 (started in 1) |
| MCP server (stretch) | 14 |

## Additions beyond the original plan

Each one was kept only because it makes the product more useful or more trustworthy.

| Addition | Part | Why it earns its place |
|---|---|---|
| SEBI Rulebook Intelligence: curated official sources with links and dates, and each flag explained (what, why, which rule, what it means for you) | 4 | The core India-specific differentiator. It separates **verified rule text** from **AI-flagged potential concerns**. |
| Explainable verdicts: why, supporting vs contradicting evidence, what couldn't be verified, confidence vs certainty | 1 (models), 5, 8 | A non-technical investor has to be able to trust and follow the result. |
| Evidence quality indicators (reliability, recency, relevance) | 3 | Shows that a source was weighed, not just found. |
| Hindi / English / Hinglish support | 2, 3, 8 | Most finfluencer content is Hinglish. |
| Downloadable source-cited report | 9 | Investors and journalists can keep and share proof. |
| Creator red-flag timeline and side-by-side comparison (explicitly not a recommendation) | 12 | Turns single checks into accountability. |
| In-app glossary and tooltips | 8 | Every technical term is explained where it appears. |

## Deliberately not added

- **Scraping YouTube or Instagram.** It breaks their terms and gets blocked (see ADR-001).
- **A "trust score" for a person.** Scores are about verifiable claims only (see ADR-003).
- **Buy/sell suggestions.** PaperTrail is not an investment adviser.

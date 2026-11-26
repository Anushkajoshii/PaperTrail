# PaperTrail API

Interactive docs: run `make dev` and open http://localhost:8000/docs. The machine-readable spec
is in [openapi.json](openapi.json) (generated from the code with `make openapi`).

## How it works: submit, then poll

Fact-checking takes seconds to minutes, so the API never makes you wait on one request:

1. `POST /checks` (or `POST /checks/upload`) stores the request, queues the job and returns
   **202 Accepted** with an `id` and a `status_url`.
2. Poll `GET /checks/{id}` every couple of seconds. While it runs you get `status`,
   `status_detail` (e.g. "Looking for evidence (round 1)") and `progress_percent`.
3. When `is_finished` is true, the response holds the full result: claims, evidence, verdicts,
   rulebook flags, registration lookup, metrics and the standard notices.

A check either completes or fails as a whole. You never get partial verdicts.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/checks` | Check pasted text (`kind: "text"`) or an article link (`kind: "article_url"`) |
| `POST` | `/checks/upload` | Check a file: `.srt` / `.vtt` subtitles, `.txt` transcript, or audio/video (needs AWS) |
| `GET` | `/checks/{id}` | Progress while running, full results when done |
| `GET` | `/creators/{handle}` | Recent checks of a creator's content, with totals |
| `GET` | `/rulebook` | Every SEBI rulebook check and its verified official sources |
| `GET` | `/glossary` | Plain-language definitions for tooltips |
| `GET` | `/health` | Service status and configuration (provider, queue mode) |

## Examples

```bash
# 1. Submit
curl -s -X POST localhost:8000/checks -H 'content-type: application/json' \
  -d '{"kind":"text","creator_handle":"@democreator","text":"Guaranteed 5% every month in my Telegram group!"}'
# -> {"id":"chk_…","status":"queued","status_url":"/checks/chk_…","poll_after_seconds":2,…}

# 2. Poll
curl -s localhost:8000/checks/chk_…

# Upload subtitles
curl -s -X POST localhost:8000/checks/upload -F file=@clip.srt -F creator_handle=@democreator
```

## Result fields worth knowing

| Field | Meaning |
|---|---|
| `check.claims[]` | Each checkable statement: English restatement, exact `quote`, type, tickers, timestamp, `why_checkable` |
| `check.evidence[]` | Passages with `stance` (supports / contradicts / context) and `quality` (reliability, recency, relevance) |
| `check.verdicts[]` | `label`, `confidence`, and `explanation` (summary, reasoning, could_not_verify, confidence_note) |
| `check.red_flags[]` | `basis` = `verified_rule` (cites `rule_source_ids`) or `potential_concern` (AI observation) |
| `check.regulatory_sources[]` | The official SEBI documents cited, with reference numbers and dates |
| `check.registration` | Register lookup result, `match_basis`, snapshot date and the "not an endorsement" note |
| `check.metrics` | LLM calls, tokens, estimated cost, duration, steps, notes |
| `notices[]` | Always show these: not financial advice, registration ≠ endorsement, confidence ≠ certainty |

## Errors

Every error has the same shape:

```json
{"error": {"code": "invalid_request", "message": "text: Value error, input kind 'text' requires 'text'"}}
```

| Status | Code | When |
|---|---|---|
| 400 | `bad_upload` | Unsupported or empty file, or not UTF-8 |
| 404 | `not_found` | Unknown check id or creator |
| 413 | `too_large` / `bad_upload` | Text over the limit (default 50,000 characters) or file over the limit |
| 422 | `invalid_request` | Missing or invalid fields |
| 429 | `rate_limited` | Too many submissions; see the `Retry-After` header (default 20 per minute per client) |

## Running modes

| Mode | Command | What happens |
|---|---|---|
| Inline (simplest) | `make dev` | The API runs each check right after responding |
| Queued (like production) | `docker compose up --build` | The API enqueues; a separate worker runs the agent |
| AWS (Part 10) | Terraform | API Gateway → Lambda (FastAPI via Mangum) → SQS → worker Lambda; DynamoDB + S3 |

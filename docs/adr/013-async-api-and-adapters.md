# ADR-013: Asynchronous API with swappable store, queue and upload adapters

- **Status:** Accepted
- **Date:** 2026-11-27

## Context

A check can take far longer than an HTTP request should wait (transcription, several searches,
LLM calls). The target is serverless AWS (API Gateway, Lambda, SQS, DynamoDB, S3), but local
development must work without an AWS account, and the code shouldn't fork between the two.

## Decision

- **Submit then poll.** `POST /checks` returns 202 with a status URL. `GET /checks/{id}` shows
  live progress from the worker's callbacks, then the result. This is the pattern in the
  original architecture: "the browser never waits on the agent".
- **Three small interfaces:** `CheckStore`, `JobQueue` and `UploadStorage`.

  | Interface | Local | AWS (Part 10) |
  |---|---|---|
  | CheckStore | SQLite (WAL) or memory | DynamoDB |
  | JobQueue | SQLite queue with visibility timeout and max attempts | SQS (with a dead-letter queue) |
  | UploadStorage | Local disk, random keys | S3 (presigned uploads) |
- **The same `process_check()`** runs in the local worker loop and, later, in the SQS-triggered
  Lambda. Processing is idempotent because SQS can deliver a message more than once.
- **Two local modes:** *inline* (`make dev`, one process) and *queued* (`docker compose`, API +
  worker), so the production shape can be exercised on a laptop.
- **Guardrails at the edge:** input size limits, allow-listed upload types with random storage
  keys, per-client rate limit with `Retry-After`, uniform error bodies, security headers, CORS.

## Consequences

- ✅ No AWS needed to run or demo the full system. Moving to AWS means new adapters, not new
  logic.
- ✅ The SQLite queue's semantics (visibility timeout, retries, dead-lettering) match SQS, so
  failure handling is tested before the cloud exists.
- ➖ SQLite suits a single machine, not production traffic. That is by design: production uses
  DynamoDB and SQS.
- ➖ The in-memory rate limiter is per process. In AWS, API Gateway throttling takes over.

## In plain English

When you submit something, PaperTrail says "got it" straight away and works on it in the
background, while the app shows a progress bar. The same code runs on a laptop today and on AWS
later; only the storage pieces change.

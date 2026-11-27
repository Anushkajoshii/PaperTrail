# ADR-017: Tracing and cost per check, with a no-op default

- **Status:** Accepted
- **Date:** 2026-11-27

## Context

A fact-check makes several AI calls, searches and page fetches across an agent graph. When a
verdict looks wrong, we need to see the exact prompt, the answer, and any retries. We also want
honest numbers for speed and cost. The app runs on Lambda, where background exporters can lose
data when the function freezes. Tests and CI must stay offline, and the budget is zero.

## Decision

- **Our own small tracing layer** (`papertrail/observability`). Pipeline code calls `span()`
  and `record_generation()`, and the current tracer is found through a context variable, so
  nothing is threaded through function signatures.
- **What is traced:**
  - one trace per check, with the check id as the trace id
  - a span per agent step, search and page fetch
  - a generation per AI call, including failed validation attempts, which are marked WARNING
    with the reason
- **Backends:**
  - no-op (the default)
  - in-memory, for tests
  - Langfuse, through its public ingestion API, as **one synchronous batch at the end of each
    check**
- **Never fatal:** export failures are logged, and text is clipped to 4,000 characters per
  field.
- **Always-on run details** stored with the check: time per step, provider, model per step,
  tokens, and cost. Free-tier providers are labelled "$0 (free tier)" rather than given an
  invented price.
- **Fleet numbers:** `make stats` / `make stats-prod` report p50/p95 latency, tokens, cost and
  failure rate from stored checks. They use the nearest-rank percentile method.

## Alternatives considered

- **The Langfuse SDK, or OpenTelemetry auto-instrumentation.** These add a background exporter
  and a larger dependency tree, and they need careful flushing on Lambda. Our calls are few and
  well defined, so a ~250-line module does the job and keeps tests simple. The ingestion API is
  older than Langfuse's OpenTelemetry endpoint, but it is still documented and supported. If it
  is retired, only the exporter needs to change.
- **CloudWatch custom metrics.** These cost money per metric each month. The same numbers come
  free from stored checks.

## Consequences

- Any verdict can be traced to its prompt, answer, model and retries in a few clicks.
- Real latency and cost figures can be published in the README from production data.
- Traces include public content that was checked, never user accounts. This is documented in
  `docs/OBSERVABILITY.md`.

## In plain English

Every check keeps a record of what the AI was asked, what it answered, how long each step took
and what it cost. That makes mistakes easy to investigate, and the speed and cost figures we
publish come from real use.

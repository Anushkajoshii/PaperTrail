# ADR-002: Pluggable LLM provider with offline mock

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

Production targets Amazon Bedrock (AWS-native, data stays in-region). However:

- Development starts before an AWS account exists.
- CI must run on every pull request without paid API calls or stored secrets.
- We want to compare models on cost and accuracy (small model vs small + strong model).

## Decision

All LLM calls go through a single `LLMProvider` interface that returns validated Pydantic
objects. The implementations are:

| Provider | Used for |
|---|---|
| `mock` (default) | Tests, CI and offline development. Deterministic, free, no network. |
| `bedrock` | Production on AWS. |
| `anthropic`, `openai_compat`, `ollama` | Optional local alternatives. |

The provider is chosen through `PAPERTRAIL_LLM_PROVIDER`. Each pipeline step (extract, judge)
can use a different model, which makes the cost/quality comparison possible.

## Consequences

- ✅ Every test runs offline in seconds, and CI needs no secrets.
- ✅ Changing models is a configuration change, not a code change.
- ➖ The mock cannot measure real accuracy. Real-model evals run separately (Parts 6 and 13).

## In plain English

The app can talk to different AI services, or to a pretend AI for testing. That way we can build
and test everything for free and switch to the real AI with one setting.

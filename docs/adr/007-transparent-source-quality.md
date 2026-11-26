# ADR-007: Transparent, rule-based source quality scores

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

Users need to see *why* a piece of evidence counts. A learned "credibility model" would be a
black box and hard to defend. Asking the LLM to rate sources would be inconsistent and costly.

## Decision

Each piece of evidence gets three scores from 0 to 1, each computed by a simple rule that can be
explained:

| Score | How it is computed |
|---|---|
| Reliability | Lookup by domain type: regulator 0.98, exchange 0.97, filing 0.92, data provider 0.85, established news 0.80, unknown 0.50, blog 0.35, social 0.15 |
| Recency | `0.5 ^ (age / half-life)`, where the half-life depends on the claim type (credentials 90 days … market facts 5 years); unknown date 0.5 |
| Relevance | Share of the claim's key terms, tickers and numbers found in the passage |

Overall = 0.5 × reliability + 0.2 × recency + 0.3 × relevance. Each score is shown as
High/Medium/Low with a plain-English reason ("High: Stock exchange", "Published about 2 years ago").

Relevance only *ranks* passages. Whether evidence supports or contradicts a claim is decided by
the LLM judge (Part 5), which is evaluated separately.

## Consequences

- ✅ Every number on screen can be explained in one sentence, and is tested.
- ✅ The domain table is easy to review and extend.
- ➖ Domain-level reliability is coarse: a weak article on a strong site still scores well. The
  judge reads the content, and the limitations page says this.

## In plain English

We score each source on three things: how trustworthy that kind of website is, how recent it is,
and how closely it talks about the claim. The rules are simple and published, so anyone can check
them.

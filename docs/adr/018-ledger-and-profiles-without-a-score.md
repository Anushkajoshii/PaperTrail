# ADR-018: Claim Ledger settled by rules, and creator profiles without a single score

- **Status:** Accepted
- **Date:** 2026-11-27

## Context

The plan called for a Claim Ledger that re-checks stock calls, and a creator page with an
"accountability score". The product rules are firm on several points:
- PaperTrail judges claims, not people.
- It never claims violations.
- It never invents data.

Free price data for Indian stocks is limited: Alpha Vantage's free tier allows 25 requests a
day, and its coverage of Indian listings is not guaranteed.

## Decision

- **Rules, not AI, settle calls.** The symbol, target, direction and deadline are parsed
  deterministically from the creator's words. Hit and missed are defined by daily highs and
  lows against the target, within the deadline, using only prices up to today. "Missed" needs
  prices covering the whole period. Otherwise the call stays open.
- **No made-up prices.** The default price provider is `none`. Demo prices exist only for
  fictional symbols. Alpha Vantage is optional and rationed: each symbol is fetched once and at
  most 20 per run.
- **A daily job** runs as a Lambda on an EventBridge schedule after Indian market close.
  Ledger entries are created by the worker, idempotently (`led_` + claim id), and a ledger
  failure never undoes a finished check.
- **Profiles show counts with sample sizes, and no score.** Percentages such as "share
  supported" and "calls that hit" appear only from 5 data points. Comparison is side by side
  with a "not a recommendation" note.
- **Tracking starts when PaperTrail first saw the call.** This is stated wherever the ledger
  is shown.

## Alternatives considered

- **A single 0–100 accountability score.** It is easy to screenshot and misuse. It hides
  sample size and which content was checked, and it reads as a judgement of a person.
  Rejected.
- **Letting the AI extract targets and deadlines.** That adds an unaudited step to the one
  place where the outcome is binary. Rejected in favour of a tested parser.
- **Scraping exchange websites for prices.** That conflicts with their terms. Rejected.

## Consequences

- Outcomes are reproducible and explainable ("reached ₹1,300 on 27 Jul 2026").
- Without a price key, calls stay open. That is honest, but the deployed ledger is less lively
  until a free key is added.
- Calls whose tracking started before Alpha Vantage's ~100-day window stay open rather than
  being guessed.

## In plain English

When someone says "this stock will hit ₹1,500 by March", PaperTrail writes it down and checks
real prices after March. Creator pages show plain counts and say when there are too few to
draw conclusions. There is no single score that labels a person.

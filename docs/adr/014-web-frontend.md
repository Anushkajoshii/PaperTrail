# ADR-014: React web app with types generated from the API contract

- **Status:** Accepted
- **Date:** 2026-11-27

## Context

Ordinary investors, not developers, are the audience. The UI has to feel like a credible
fintech product, explain every concept in plain language, work on phones, and never drift from
the API it depends on.

## Decision

- **React 19 + Vite + TypeScript + Tailwind CSS 4**, as in the original plan: fast to build,
  widely known, and a static build that can be hosted anywhere (Vercel).
- **One source of truth for data shapes.** The FastAPI app generates `docs/openapi.json`, and
  `openapi-typescript` turns it into `web/src/api/schema.d.ts`. API response fields with
  defaults are marked required, so the types are exact. CI fails if the generated file is stale.
- **Poll, don't stream.** The results page polls `GET /checks/{id}` every 1.5 s and shows a stepper
  with the worker's live progress message. This is simple, works through API Gateway, and needs
  no websockets.
- **Explainability in the UI:**
  - each claim card shows verdict, confidence meter, summary, numbered sources, the reasoning
    steps (with internal ids replaced by "source N"), what couldn't be verified, and the
    confidence note
  - official SEBI flags (amber, book icon) look different from AI potential concerns (blue,
    sparkle icon)
- **Glossary tooltips** come from `GET /glossary`, so wording is shared with the API and docs.
- **English/Hindi interface** for navigation, landing page, form and progress steps. Analysis
  content keeps its original language, and quotes are always shown as spoken.
- **Accessibility:** icons and text (never colour alone), semantic landmarks, skip link,
  keyboard tooltips, ARIA on progress and confidence meters.

## Consequences

- ✅ A backend change that breaks the UI is caught at compile time.
- ✅ Tests run against a real check produced by the backend, not hand-written fixtures.
- ➖ Hindi covers interface text only. Translating analysis results is a possible later addition.
- ➖ Polling every 1.5 s is slightly wasteful. That's fine at this scale.

## In plain English

The website is built with standard, well-known tools, and it automatically knows the exact shape
of the data the server sends, so the two can't silently get out of sync. Everything technical has
a hover explanation, and the main screens can be switched to Hindi.

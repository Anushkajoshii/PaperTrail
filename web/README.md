# PaperTrail web app

React 19 + Vite + TypeScript + Tailwind CSS 4. It talks to the PaperTrail API.

## Run it

```bash
make dev                 # in the repo root: API on http://localhost:8000
cd web && npm install
npm run dev              # http://localhost:5173 (calls to /api are proxied to the API)
```

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Type-check and build to `dist/` |
| `npm test` | Component and page tests (Vitest + Testing Library) |
| `npm run gen:api` | Regenerate `src/api/schema.d.ts` from `../docs/openapi.json` |

After changing the API, run `make openapi` in the repo root and then `npm run gen:api`. CI fails if
the generated types are out of date.

## Structure

```
src/
  api/          client.ts (fetch wrapper with friendly errors), schema.d.ts (generated), types.ts
  components/   Layout, VerdictBadge, ClaimCard + ConfidenceMeter, Evidence, FlagCard,
                ProgressView, ResultsView, Term (glossary tooltip), States
  pages/        Landing, NewCheck, CheckPage (progress -> results), RulebookPage,
                CreatorPage, GlossaryPage, NotFound
  lib/          verdict styles, English/Hindi interface strings, glossary context
  test/         tests and a real check fixture produced by the backend
```

## Design principles

- **Plain language first.** Every technical term has a tooltip, and every verdict says why.
- **Colour is never the only signal.** Verdicts always pair an icon with a text label.
- **Accessible.** Skip link, keyboard-reachable tooltips, labelled progress bar and confidence
  meter, `aria-expanded` on disclosures.
- **Honest.** Official SEBI flags and AI observations look different. Demo data is labelled.
  Failed checks never show partial results.

## Deploying

Set `VITE_API_URL` to the API's public URL (API Gateway in Part 10) and deploy `dist/` to any
static host, for example Vercel.

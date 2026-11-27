# Development guide

## Setup

```bash
make install      # uv sync --all-extras + pre-commit hooks
make test         # pytest with coverage
make lint         # ruff check + format check
```

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/). No API keys and no AWS account are
needed for development or tests.

## Project layout

```
papertrail/
  models.py         # Core data contract (Claim, Evidence, Verdict, RedFlag, Check)
  config.py         # Settings from env vars / .env
  llm/              # Pluggable LLM layer
    base.py         #   Provider protocol, generate_structured (validate + retry), usage/cost
    mock.py         #   Offline deterministic provider (default)
    anthropic_provider.py  # Claude via Anthropic API and Amazon Bedrock
    http_providers.py      # OpenAI-compatible endpoints, Ollama
    factory.py      #   Provider + per-step model selection
    pricing.py      #   Approximate token prices for cost-per-check
  text/             # Language detection, sentence splitting, Indian number parsing
  agent/
    prompts.py      #   Versioned prompts with injection-safe data tags
    extract.py      #   Claim extraction with grounding
    heuristics.py   #   Rule-based extractor (mock backend and eval baseline)
    research.py     #   Search -> safe fetch -> passages -> quality-scored candidates
    judge.py        #   Verdict rubric, citations, capped + explained confidence
    graph.py        #   LangGraph agent: ingest..rulebook, evidence loop, step guard
    run.py          #   CLI: full check with a readable report (make demo)
  tools/
    transcribe.py   #   Amazon Transcribe (en-IN/hi-IN) + .srt/.vtt/.txt files
    search.py       #   Tavily live search + offline demo fixture; social media excluded
    fetch.py        #   Safe page fetch: SSRF guard, limits, robots.txt, readable text
    untrusted.py    #   Prompt-injection sanitising and data-tag wrapping
    source_quality.py  # Reliability / recency / relevance scores + plain labels
    data/           #   Offline demo search results (.test domains only)
  rulebook/
    data/sebi_sources.yaml  # Curated, verified official SEBI sources
    sources.py      #   Load/validate the registry; staleness check
    rules.py        #   Deterministic red-flag rules (EN/Hinglish/Hindi) + rule catalog
    concerns.py     #   AI potential concerns with code-level guards; check_rulebook()
    registry.py     #   SEBI register snapshot: parse, match, lookup (no contact data)
    catalog_doc.py  #   Generates docs/SEBI_RULEBOOK.md
  api/
    app.py          #   FastAPI app: routes, limits, errors, security headers
    schemas.py      #   Request/response models (drive the OpenAPI docs)
    main.py         #   uvicorn entry point
    lambda_handler.py  # AWS Lambda entry point (Mangum)
  store/            # CheckStore / JobQueue / UploadStorage (SQLite + disk locally)
  worker.py         # Runs queued checks with live progress
  content/glossary.yaml  # Plain-language terms for tooltips
  ledger/           # Filled in a later part
examples/           # Synthetic sample transcripts
tests/              # Unit tests (all offline)
docs/               # ADRs, roadmap, plain-English guide, limitations
```

## Choosing an LLM provider

Set `PAPERTRAIL_LLM_PROVIDER` in `.env`:

| Value | Needs | Notes |
|---|---|---|
| `mock` (default) | nothing | Rule-based. For development and tests, not for accuracy. |
| `anthropic` | `ANTHROPIC_API_KEY` (or `ant auth login`) | Haiku 5.5 extracts, Opus 5.5 judges |
| `bedrock` | AWS credentials (Part 10) | Same models via Amazon Bedrock |
| `openai_compat` | `PAPERTRAIL_OPENAI_COMPAT_BASE_URL`, key, model names | Any OpenAI-compatible API |
| `ollama` | Ollama running locally, model names | Free, local, slower |

Override models per step with `PAPERTRAIL_EXTRACT_MODEL` and `PAPERTRAIL_JUDGE_MODEL`.

## Try claim extraction

```bash
uv run python -m papertrail.agent.extract examples/hinglish_reel.txt
```

The output lists each claim (type, exact quote, tickers, why it is checkable), any claims dropped
(with the reason), and the estimated cost.

## Run the API

```bash
make dev                         # http://localhost:8000/docs (checks run in-process)
PAPERTRAIL_QUEUE_MODE=sqlite make dev   # API only enqueues ...
make worker                      # ... and this runs them
docker compose up --build        # both, in containers
```

## Run the web app

```bash
make dev                         # API on :8000
cd web && npm install && npm run dev    # UI on :5173
cd web && npm test               # web tests
```

See [web/README.md](../web/README.md).

## Run a full check

```bash
make demo
uv run python -m papertrail.agent.run examples/english_post.txt --json > check.json
uv run python -m papertrail.agent.run https://example.com/article --creator-name "Name"
```

Agent limits: `PAPERTRAIL_MAX_AGENT_STEPS` (40), `PAPERTRAIL_MAX_SEARCH_ROUNDS` (2),
`PAPERTRAIL_PAGES_TO_FETCH_PER_CLAIM` (2).

## Evidence tools

| Setting | Values |
|---|---|
| `PAPERTRAIL_SEARCH_PROVIDER` | `offline` (default) or `tavily` (needs `PAPERTRAIL_TAVILY_API_KEY`) |
| `PAPERTRAIL_MEDIA_BUCKET` | S3 bucket for audio/video transcription (Part 10). Without it, upload `.srt`/`.vtt`/`.txt`. |

Quick check of the fetcher on a real page (makes one network request):

```bash
uv run python -c "from papertrail.tools.fetch import PageFetcher; p = PageFetcher().fetch('https://www.sebi.gov.in/'); print(p.title, len(p.text))"
```

## SEBI rulebook

- Add or update a source in `papertrail/rulebook/data/sebi_sources.yaml` only after checking
  it on sebi.gov.in. Set `verified_on` and an honest `verification_level`.
- After changing rules or sources run `make rulebook-docs`. A test fails if the doc is stale.
- Register snapshot (optional, local): save SEBI's public register pages from your browser, then

```bash
uv run python -m papertrail.rulebook.registry import ra_page1.html ra_page2.html --category research_analyst
uv run python -m papertrail.rulebook.registry lookup "Creator Name"
```

## Conventions

- Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `ci:`, `infra:`, `eval:`, `refactor:`).
- One branch per roadmap part (`part-N/name`), merged through a PR after CI passes.
- Prompts are versioned in `papertrail/agent/prompts.py`. Bump the version when the wording changes.
- User-facing text must explain concepts in plain language (see `docs/PLAIN_ENGLISH.md`).

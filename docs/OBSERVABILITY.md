# Observability: tracing, cost and speed

Every check records how it ran, so it can be debugged and its cost explained. There are three
levels, each optional except the first.

## 1. Run details on every check (always on)

Each finished check stores `metrics`, shown on the results page under **About this check** and
at the end of every report:

| Field | Meaning |
|---|---|
| `duration_ms` | Total time from start to finish |
| `step_ms` | Time spent in each agent step: reading, finding claims, SEBI register, evidence search, weighing evidence, rulebook |
| `llm_calls`, `total_tokens` | How many AI calls were made and how much text they processed |
| `llm_provider`, `models` | Which AI was used, and which model did each step |
| `cost_usd` | Estimated cost from list prices. Free-tier providers (Groq, Ollama, mock) are shown as **$0 (free tier)** |
| `prompt_versions` | Which prompt version produced the result (for reproducibility) |

## 2. Traces in Langfuse (optional, free)

With Langfuse keys set, every check becomes one **trace**, and its id is the check id, so you
can search for `chk_...`:

```
check (chk_37c8a7e8773e)                 status, claims, verdict counts, cost, tokens
├─ ingest                                 span
├─ extract                                span
│  └─ extract: ClaimExtractionOutput      generation: prompt, output, model, tokens, latency
├─ registration                           span
├─ research                              span (round 1)
│  ├─ search  "Nifty 50 returns 2023"     span: query and results
│  └─ fetch   https://…                   span
├─ research                              span (round 2)
├─ judge
│  ├─ judge: JudgeOutput                  one generation per claim
│  └─ judge: JudgeOutput   ⚠ WARNING      output failed validation, retried with feedback
└─ rulebook
   └─ judge: PotentialConcernsOutput
```

What this makes visible:
- the exact prompt and answer behind any verdict
- retries after an answer broke a rule (shown as warnings)
- slow searches or pages
- token use per step

**Turn it on (free, no card):**
1. Sign up at https://cloud.langfuse.com and create a project, for example `papertrail`.
2. Under **Settings → API Keys**, create a key pair.
3. Locally, add both keys to `.env`:
   ```
   PAPERTRAIL_LANGFUSE_PUBLIC_KEY=pk-lf-...
   PAPERTRAIL_LANGFUSE_SECRET_KEY=sk-lf-...
   ```
   If your project is in the US region, also set `PAPERTRAIL_LANGFUSE_HOST=https://us.cloud.langfuse.com`.
4. For the deployed app, copy them into AWS SSM. Values are never printed:
   ```bash
   AWS_PROFILE=portfolio uv run python scripts/push_secrets.py
   ```

How it works:
- Events are sent in **one batch per check**, through Langfuse's public ingestion API, when
  the check ends.
- This suits Lambda: nothing is lost when the function freezes, and there are no background
  threads.
- Export errors are logged and never fail a check.
- Prompt and answer text is clipped to 4,000 characters per field.

**Privacy:** traces contain the checked content (public posts or videos) and the AI's answers.
They contain no user accounts, IP addresses or contact details. Langfuse's free cloud tier
keeps data for a limited time. Self-host Langfuse if you need the data to stay elsewhere.

## 3. Speed and cost across many checks

```bash
make stats         # local checks
make stats-prod    # the deployed app's DynamoDB table (needs `aws login`)
```

This prints:
- p50 and p95 time per check
- AI calls, mean and p95 tokens
- cost per check and failure rate
- providers used, and the step that took the most time overall

`--json` gives the same data as machine-readable output.

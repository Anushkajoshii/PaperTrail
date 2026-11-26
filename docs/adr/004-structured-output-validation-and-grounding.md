# ADR-004: Structured output, validation with retry, and quote grounding

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

LLMs sometimes return malformed output, and sometimes invent content. For a fact-checker, an
invented claim is the worst possible failure: it would attribute words to a real creator that
they never said.

## Decision

Three layers, from cheapest to strictest:

1. **Structured output at the provider.** Claude (API and Bedrock) uses native structured outputs
   (`output_config.format` with a JSON schema generated from the Pydantic model). OpenAI-compatible
   endpoints and Ollama get the same schema through their JSON-schema modes.
2. **Pydantic validation, with one retry.** Each result is validated against a Pydantic model that
   carries product rules a JSON schema cannot express. If validation fails, the exact errors go
   back to the model once (`generate_structured`). If it still fails, the step fails loudly. We
   never "repair" data silently.
3. **Grounding against the source.** Every extracted claim must quote the transcript. The quote
   has to appear in the transcript, either exactly or with a fuzzy match of at least 90/100
   (rapidfuzz `partial_ratio`) to tolerate transcription noise. **Numbers must match exactly**, so
   "₹1500" can never ground "₹2500". Ungrounded claims are dropped and logged with a reason, so
   evals can count them.

The LLM-facing schema (`ExtractedClaim`) is deliberately *lenient on cosmetic issues*, such as
"Stock Call" vs `stock_call` or "INFY.NS" vs "INFY", and *strict on substance*, such as a missing
quote.

## Consequences

- ✅ Hallucinated claims cannot reach users. This is measurable: "dropped as ungrounded" is
  reported by the eval runner (Part 6).
- ✅ Model-agnostic: the same guarantees hold for every provider.
- ➖ A retry costs an extra call when it happens. Retries are visible in usage logs.
- ➖ Heavily paraphrased quotes, such as a model translating Hindi into English inside `quote`, are
  dropped. The prompt tells the model to keep quotes verbatim.

## In plain English

The AI must answer in a fixed format, and its answer is checked. Every claim has to point to the
exact words in the video or post. If it can't, we throw that claim away instead of showing it.

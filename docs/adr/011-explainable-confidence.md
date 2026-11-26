# ADR-011: Confidence is capped by evidence quality and always explained

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

LLMs are often over-confident, and a bare "92% confident" means little to a non-expert. It can
also be misread as "92% likely to be true". Users need to see *why* the system is confident, and
the score must not exceed what the evidence can bear.

## Decision

- The judge proposes a confidence (0–1) **in its assessment**.
- Code caps it: `cap = 0.35 + 0.6 × best quality of the cited evidence`, minus 0.15 when sources
  conflict. "Not verifiable" verdicts are capped at 0.6, and a verdict with no evidence at 0.3–0.35.
  The final value is `min(proposed, cap)`.
- If the LLM's label is not backed by the evidence it cited (e.g. "supported" with no supporting
  passage), the label is downgraded to "not verifiable" and the reason is shown.
- Every verdict carries a plain-language `confidence_note`: the band (High/Medium/Low), how many
  sources, how strong the best one is, whether sources conflict, whether the score was capped,
  and the standard notice that confidence is not certainty.
- Credential claims are scored from the register lookup: 0.9 for a registration-number match,
  0.7 for a name match. A miss is "not verifiable", never "contradicted".

## Consequences

- ✅ A blog post can never produce a "high confidence" verdict, however sure the model sounds.
- ✅ Calibration can be measured and tuned in the eval suite (Parts 6 and 13).
- ➖ The cap formula is a hand-set rule. Its constants are documented and will be tuned with
  eval data.

## In plain English

The "confidence" shown is how sure PaperTrail is about its own reading of the evidence, and it
can never be higher than the evidence deserves. Every score comes with a sentence explaining it.

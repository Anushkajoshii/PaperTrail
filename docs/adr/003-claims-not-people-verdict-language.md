# ADR-003: Verdicts about claims, never people

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

PaperTrail comments on real, identifiable creators. Wrong or overreaching language could be
defamatory, and could mislead investors. AI systems are also prone to confidently inventing
facts, including regulations that do not exist.

## Decision

1. **Verdicts apply to claims.** The only verdicts are `supported`, `contradicted`, `misleading`
   and `not_verifiable`. No verdict, score or label is ever attached to a person's character.
2. **Careful wording.** "No evidence found for this claim", never "this person is a scammer".
3. **Two kinds of regulatory flag, always labelled:**
   - `verified_rule`: quotes an official SEBI document from our curated source registry, with its
     URL and publication or effective date.
   - `potential_concern`: an AI observation that *may* be relevant. It is never described as a
     violation.
   A flag may only be `verified_rule` if it links to a source in the curated registry. This is
   enforced in the data model, so the AI cannot invent a regulation.
4. **Confidence is not certainty.** Every verdict carries the model's confidence *in its
   assessment* and a separate, fixed statement that it is not a guarantee of truth.
5. **Standard notices** are always shown: not financial advice, and registration ≠ SEBI
   endorsement.

## Consequences

- ✅ Legally safer and more trustworthy. Interviewers recognise this as responsible-AI design.
- ➖ Some results feel less dramatic ("not verifiable" instead of "fake"). This is intended.

## In plain English

We judge statements, not people. We only say "SEBI rule" when we can link to the actual SEBI
document. Anything else is clearly marked as "might be worth a look".

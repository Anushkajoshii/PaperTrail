# ADR-008: SEBI rulebook: verified rules vs AI potential concerns

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

The SEBI rulebook is PaperTrail's main differentiator, and also its biggest risk. An AI that
"knows" SEBI rules from memory will sometimes invent regulations, misquote dates, or describe a
creator as breaking the law. Any of these would mislead investors and could be defamatory.

SEBI's rules also change. While building this, we found that on 8 May 2026 SEBI changed the
"education" condition in circular CIR/2025/11 from "price data of the preceding three months" to
"preceding thirty days". A system built from memory would have been wrong.

## Decision

1. **A curated source registry** (`papertrail/rulebook/data/sebi_sources.yaml`):
   - Only `sebi.gov.in` / `investor.sebi.gov.in` documents (enforced by the model validator).
   - Each entry records its reference number, dates, plain-language summary, key points,
     provisions, `verified_on` date and **verification level**: read in full, title/date only,
     or wording quoted in SEBI orders. The UI shows the level.
   - Entries go stale after 180 days and are listed for re-verification.
2. **Deterministic rules** (`rules.py`) detect patterns in English, Hinglish and Hindi. Every
   rule cites registry ids, checked at import time, and explains what was detected, why it
   matters and what an investor should know.
3. **AI potential concerns** (`concerns.py`) cover the long tail. They are always labelled as AI
   observations. The data model forbids them from naming a provision. Code drops ungrounded quotes,
   accusatory words and unknown source ids.
4. **Language:** flags describe what was *said* and what SEBI's material *says*. We never write
   "violated". "Not found in our copy of the register" is never "unregistered". Registration is
   never presented as endorsement.
5. **Applicability is stated honestly.** Regulation 16A of the Intermediaries Regulations
   restricts SEBI-*regulated entities* from associating with people who give unregistered advice
   or make unpermitted performance claims. PaperTrail cites it to explain what SEBI treats as
   prohibited activity, not to say that a creator is bound by it.
6. **What we deliberately skip:** checks we could not ground in a verified source (for example
   "missing disclaimer" for unregistered creators).

## Consequences

- ✅ Every "official rule" label is backed by a link, a date and a reference number that were
  checked against SEBI's own site.
- ✅ `docs/SEBI_RULEBOOK.md` is generated from the code, and a test keeps it in sync.
- ➖ Keeping sources current is a manual task. The staleness check makes it visible.
- ➖ Pattern rules can over- or under-match (for example a negated "no guarantees"). Known cases
  are documented in the tests and in LIMITATIONS.

## In plain English

We only say "SEBI rule" when we can link to the actual SEBI document and have checked it
ourselves. Anything the AI notices on its own is clearly marked as "might be worth a look", and it
is never allowed to accuse anyone.

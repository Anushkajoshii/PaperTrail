# What PaperTrail cannot do

Being honest about limits is part of the product. The app shows this list too.

1. **It cannot judge intent or honesty.** It checks statements against evidence. It never decides
   whether a person meant to mislead.
2. **It cannot prove a legal violation.** Only SEBI and the courts can decide that. PaperTrail
   shows official rule text next to what was said and labels AI observations as *potential
   concerns*.
3. **It only knows what it can find.** Private Telegram groups, paid courses and deleted posts are
   usually out of reach. Missing evidence gives "Not verifiable", never "false".
4. **The AI can make mistakes.** Transcription can mishear Hinglish. Extraction can miss a claim.
   Judging can misread a source. Measured error rates are published in the README.
5. **The registry is a snapshot.** The SEBI list is refreshed periodically. A very recent
   registration or cancellation may not show yet. Always confirm on SEBI's website.
6. **Price data is unofficial.** The Claim Ledger uses free market data (yfinance), which can have
   gaps or adjustments.
7. **It does not scrape social platforms.** You upload the clip or paste the text (see ADR-001).
8. **Language detection is approximate.** Very short or unusual Hinglish can be labelled English.
   This only affects hints given to the AI, not which claims are checked.
9. **Exact quotes only.** If a creator's words were transcribed very differently, a real claim can
   be dropped as "not found in transcript". We prefer missing a claim to inventing one.
10. **It is not financial advice.** It never recommends buying or selling anything, and creator
   comparisons are not recommendations.

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
6. **Price data is limited.** By default the Claim Ledger has no price source, so calls stay
   unsettled rather than being settled with made-up numbers. With a free Alpha Vantage key it
   uses BSE daily prices, which cover about the last 100 trading days and can have gaps.
7. **It does not scrape social platforms.** You upload the clip or paste the text (see ADR-001).
8. **Language detection is approximate.** Very short or unusual Hinglish can be labelled English.
   This only affects hints given to the AI, not which claims are checked.
9. **Exact quotes only.** If a creator's words were transcribed very differently, a real claim can
   be dropped as "not found in transcript". We prefer missing a claim to inventing one.
10. **Source scores are about the website, not the article.** A weak article on a strong news
    site still gets a high reliability score. The AI judge reads the actual text.
11. **PDF documents are not read yet.** Many exchange filings are PDFs. Support is planned.
12. **Offline demo mode uses sample data.** Without a search key, results come from a small set of
    clearly labelled demo sources on `.test` addresses, never real ones.
13. **Pattern rules are not perfect.** Common negations ("returns are not guaranteed", "I'm not
    SEBI-registered", "no hurry") and look-alikes ("our family WhatsApp group") are handled, but
    unusual phrasing can still slip through or be flagged by mistake. Each flag shows the exact
    words, so you can judge for yourself.
14. **The SEBI register copy is a snapshot, and the live demo has none.** When a copy is loaded,
    its date is shown with every result; automated refreshing is not switched on. The deployed
    demo does not include a copy, so registration shows "not checked". Brand names often
    differ from registered names.
15. **SEBI rules change.** Sources are re-checked periodically (each shows its "last checked"
    date). The Research Analysts Regulations may have been amended after the version we read.
16. **Predictions wait for their deadline.** A stock target is "not verifiable" on the day it is
    checked. The Claim Ledger settles it later, starting from when PaperTrail first saw it,
    which may be after the creator posted it.
17. **Offline mode is a demo, not an assessment.** Without a real AI model, verdicts come from
    simple number-matching rules against demo data. Accuracy is measured with real models
    ([docs/EVALUATION.md](EVALUATION.md)).
18. **The test set is synthetic and has one annotator.** Golden set v2 has 95 claims about
    fictional companies, labelled by one person, with no agreement score. Real people from SEBI
    orders are left out on purpose.
19. **Hindi covers the interface, not the analysis.** Explanations are in English. Original quotes
    are always shown as spoken.
20. **The deployed AI is a free open model.** The live site uses gpt-oss models on Groq's free
    tier. It is weakest at the "misleading" label: technically true but cherry-picked claims can
    be marked "supported", and guaranteed-return promises "contradicted"
    ([model comparison](../evals/reports/model-comparison.md)). Free-tier rate limits make busy
    moments slower.
21. **Uploads are limited in the deployed version.** Files over 4 MB are rejected, because of
    Lambda's request size limit, and audio or video transcription has not been tested on the
    deployed account yet. Subtitles (.srt/.vtt) and pasted text work.
22. **It is not financial advice.** It never recommends buying or selling anything, and creator
    comparisons are not recommendations.

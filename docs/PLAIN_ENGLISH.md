# PaperTrail in plain English

This page explains every concept PaperTrail uses without jargon. The same explanations appear as
tooltips inside the app.

## The four verdicts

| Verdict | Meaning | Example |
|---|---|---|
| ✅ **Supported** | Reliable sources agree with the claim. | "Nifty 50 closed above 24,000 on 1 Oct 2024." Exchange data confirms it. |
| ❌ **Contradicted** | Reliable sources say the opposite. | "This fund never had a losing year." Its factsheet shows a loss in 2022. |
| ⚠️ **Misleading** | Partly true, but missing context changes the meaning. | "Stock X gave 200%!" True, but only over one cherry-picked month. |
| ❔ **Not verifiable** | We could not find enough reliable evidence either way. | "My students made ₹10 lakh last month." No public record exists. |

"Not verifiable" is **not** an accusation. It only means the evidence isn't available to us.

## Confidence vs certainty: the most important distinction

- **Confidence** is how sure PaperTrail is about *its own assessment*, based on how much good
  evidence it found and how well it agrees.
- **Certainty** that the claim is true is something PaperTrail never gives. Markets change,
  sources can be wrong, and an AI can make mistakes.

So "Contradicted, high confidence" means: *the evidence we found clearly disagrees with the
claim.* It does **not** mean "this is 100% proven false" or "this person lied".

## How a check works, step by step

1. **Read** the content (text, article link, subtitles, or audio/video).
2. **Find claims**: the checkable statements, each with the exact words used.
3. **Check registration**: look the creator up in our copy of SEBI's register.
4. **Research**: search trustworthy sources and pick the most relevant passage from each. If
   nothing relevant turns up, try one broader search.
5. **Judge**: weigh the evidence for each claim and explain the verdict.
6. **Rulebook**: compare what was said with official SEBI rules and guidance.

If anything goes wrong along the way, you get an error message, never half a result.

## Glossary

| Term | Plain meaning |
|---|---|
| **Claim** | One checkable statement of fact, e.g. a number, a date or a past result. Opinions ("I like this stock") are not claims. |
| **Claim extraction** | The step where the AI reads the transcript and lists the checkable claims. |
| **Evidence** | A piece of text from a source (news, exchange data, official filings) that relates to a claim. |
| **Context evidence** | A source that is relevant background but neither confirms nor refutes the claim, e.g. SEBI's guidance that returns can't be guaranteed. |
| **Confidence note** | One sentence under each verdict explaining its confidence: how many sources, how strong they are, and whether they disagree. |
| **Supporting / contradicting evidence** | Evidence that agrees with the claim / evidence that disagrees with it. |
| **Source reliability** | How trustworthy the *type* of source is. Exchange or regulator websites rank highest, anonymous blogs lowest. |
| **Recency** | How recent the source is. Old evidence can be outdated for market claims. |
| **Relevance** | How directly the source talks about *this exact* claim. |
| **Evidence quality** | Each source is marked High, Medium or Low on three things: how trustworthy that kind of website is (reliability), how recent it is (recency), and how closely it talks about the claim (relevance). |
| **Demo data** | Sample sources used when PaperTrail runs without internet search. They are always labelled "(demo data)" and use made-up `.test` web addresses. |
| **Citation** | A link to the exact source used, so you can check it yourself. |
| **SEBI** | Securities and Exchange Board of India, the regulator for India's securities markets. |
| **Investment Adviser (IA)** | A person or firm registered with SEBI to give personalised investment advice for a fee. |
| **Research Analyst (RA)** | A person or firm registered with SEBI to publish research and stock recommendations. |
| **Registered ≠ endorsed** | SEBI registration means someone met SEBI's eligibility requirements. It does **not** mean SEBI approves or guarantees their advice. |
| **Registration number** | The number SEBI gives a registered adviser or analyst. Investment advisers' numbers start with **INA**, research analysts' with **INH**. You can check them on SEBI's website. |
| **Prohibited activities** | SEBI's term (in its 2024 'finfluencer' rules) for two things registered firms must not be linked with: giving securities advice without registration, and making claims of returns or performance without SEBI's permission. |
| **Our copy of SEBI's register** | A saved list of registered advisers and analysts (names and numbers only). It has a date, can be out of date, and "not found" in it never means "unregistered". |
| **Red flag** | A statement that official SEBI rules or investor-awareness material warn about, such as "guaranteed returns". |
| **Verified rule vs potential concern** | A *verified rule* is quoted from an official SEBI document we link to. A *potential concern* is something the AI noticed that **may** be relevant. It is clearly labelled as such and is never presented as a violation. |
| **Claim Ledger** | A running record of a creator's past stock calls, re-checked against actual prices over time. |
| **Accountability profile** | A summary of how a creator's *checkable* past claims held up. It is not a judgement of the person. |
| **Transcript** | The spoken words of a video or audio turned into text. |
| **LLM** | "Large Language Model", the kind of AI that reads and writes text (like ChatGPT or Claude). |
| **Grounding** | Checking that every claim the AI found really appears, word for word, in the video or post. Claims that can't be traced back to the exact words are thrown away. |
| **Hinglish** | Hindi and English mixed together, often written in English letters ("yeh stock pakka double hoga"). PaperTrail understands English, Hindi and Hinglish. |
| **Why checkable** | A one-line note on each claim saying what kind of public record could confirm or refute it. |
| **Golden set** | A fixed list of practice examples with known correct answers, used to measure how often PaperTrail gets it right. |
| **Accuracy / F1** | Accuracy is the share of answers that were right. F1 balances "didn't miss things" against "didn't raise false alarms". |
| **Calibration** | Whether confidence can be trusted: if PaperTrail says "80% confident" on 10 claims, about 8 should be right. |
| **Mock mode** | A test mode where the AI is replaced by fixed, predictable answers, so the app can run without internet or API keys. |
| **Prompt injection** | A trick where a web page hides instructions meant for the AI ("ignore your rules…"). PaperTrail treats all fetched text as data, never as instructions. |

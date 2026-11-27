# ADR-015: Reports as print-ready HTML and Markdown, not server-side PDF

- **Status:** Accepted
- **Date:** 2026-11-27

## Context

Investors and journalists need to keep and share a fact-check as proof: a document with every
claim, verdict and source. A PDF is the obvious format, but server-side PDF generation has real
costs. Hindi in Devanagari needs complex text shaping and bundled fonts, and engines like
WeasyPrint or headless Chrome add system libraries that bloat the Docker image and the Lambda
package.

## Decision

- **One report structure, several renderers.** `build_report(check)` orders claims most-serious
  first and numbers evidence as [1]…[N] and official SEBI documents as [S1]…[Sn]. Internal ids in
  the AI's reasoning become citation numbers.
- **HTML for print / PDF:** a self-contained page (no external resources) with print CSS (A4,
  page-break aware). "Save as PDF" opens it with the browser's print dialog, and browsers render
  Hindi perfectly.
- **Markdown** for archiving, emailing or pasting into notes.
- **Security:** reports contain third-party text, so:
  - HTML autoescaping is forced on (a test caught that extension-based autoescaping skipped
    `.html.j2`)
  - Markdown special characters are escaped
  - links must be http(s)
  - responses carry a strict Content-Security-Policy
- **Sharing:** WhatsApp share sends a short, neutral summary (claims and counts, never claims
  about the person) plus the link.

## Consequences

- ✅ No heavy dependencies; Hindi renders correctly; identical content across formats.
- ✅ Every statement in a report traces to a numbered source.
- ➖ The PDF is made by the user's browser, not the server. If needed later, headless Chromium
  in a separate Lambda could produce PDFs directly.

## In plain English

You can download a full report of any check, with every claim and every source numbered. To get
a PDF, click "Save as PDF" and your browser makes one, with Hindi text displayed correctly.

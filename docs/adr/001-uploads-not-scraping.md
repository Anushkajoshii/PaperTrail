# ADR-001: Uploads, not scraping

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

Most finfluencer content lives on YouTube and Instagram. The obvious approach is to download
videos from a pasted link. However:

- Downloading media breaks the YouTube and Instagram terms of service.
- These platforms actively block downloads from cloud IP ranges, including AWS, so a scraper that
  works on a laptop fails in production.
- Scrapers break whenever the platform changes, which creates constant maintenance.

## Decision

PaperTrail accepts content the user already has:

- an uploaded video clip or screen recording
- an audio file
- pasted text (a caption, a tweet or post, a forwarded message)
- an article URL (public web pages, fetched politely and stored only as extracted text)

For YouTube links, we use the official **YouTube Data API** for *metadata only* (title, channel,
publish date), never to download media.

## Consequences

- ✅ Legally clean, reliable in production, and no cat-and-mouse with platform blocking.
- ✅ Users can check content from any source, including WhatsApp forwards and Telegram screenshots.
- ➖ Slightly more friction: the user has to upload a clip. The UI reduces this with a guided
  upload screen and screen-recording tips.

## In plain English

We don't secretly download videos from YouTube or Instagram, which would break their rules and
stop working. You give us the clip or the text, and we check it.

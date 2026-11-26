# Architecture Decision Records

Short notes on each significant design choice: the context, the decision, and its consequences.
New ADRs copy [000-template.md](000-template.md).

| ADR | Title | Status |
|---|---|---|
| [001](001-uploads-not-scraping.md) | Uploads, not scraping | Accepted |
| [002](002-pluggable-llm-with-offline-mock.md) | Pluggable LLM provider with offline mock | Accepted |
| [003](003-claims-not-people-verdict-language.md) | Verdicts about claims, never people | Accepted |
| [004](004-structured-output-validation-and-grounding.md) | Structured output, validation with retry, and quote grounding | Accepted |
| [005](005-per-step-model-selection.md) | A small model extracts, a stronger model judges | Accepted |
| [006](006-untrusted-web-content.md) | Treat every fetched page as hostile (SSRF + prompt injection) | Accepted |
| [007](007-transparent-source-quality.md) | Transparent, rule-based source quality scores | Accepted |
| [008](008-sebi-rulebook.md) | SEBI rulebook: verified rules vs AI potential concerns | Accepted |
| [009](009-sebi-register-snapshot.md) | SEBI register: minimal local snapshot, careful matching | Accepted |

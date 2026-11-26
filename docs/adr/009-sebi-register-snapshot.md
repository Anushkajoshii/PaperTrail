# ADR-009: SEBI register: minimal local snapshot, careful matching

- **Status:** Accepted (automated refresh: pending review)
- **Date:** 2026-11-26

## Context

To say whether a creator is a SEBI-registered investment adviser (IA) or research analyst (RA),
we need SEBI's public list of registered intermediaries. That list also shows personal contact
details (emails, phone numbers, addresses) of individual registrants. The original plan says to
check the site's terms before caching it.

## Decision

- **Data minimisation:** the parser keeps only *name, registration number, category and validity
  dates*. Contact details are never stored, logged or shown.
- **Snapshot, not live scraping:** lookups run against a local JSON snapshot
  (`data/sebi_registry/snapshot.json`, git-ignored). It is built by importing pages saved from
  SEBI's public website (`python -m papertrail.rulebook.registry import ...`).
- **Automated refresh is pending.** A weekly refresh job (Part 10) will be enabled only after
  SEBI's website terms have been reviewed and the project owner approves it. Until then the
  snapshot date is shown with every result.
- **Matching:**
  1. INA/INH registration numbers mentioned in the content are matched exactly (strong).
  2. Otherwise the creator's name is fuzzy-matched (rapidfuzz `token_sort_ratio` ≥ 92) after
     removing suffixes like "Pvt Ltd". Proprietor and trade names are matched too. The result
     records `match_basis="name"`, and the UI asks the user to confirm the number.
  3. Expired registrations are reported as such.
- **Wording:** no match gives `not_found`, explained as "not found in our copy of the register
  dated …, which is not proof that the person is unregistered".

## Consequences

- ✅ No personal data leaves SEBI's site through us. Tests assert contact fields are dropped.
- ✅ Lookups are fast, offline and testable. The repo contains only a synthetic fixture.
- ➖ The snapshot can be out of date. The date is always displayed, and users are pointed to
  https://www.sebi.gov.in/intermediaries.html to confirm.
- ➖ Creators often use a brand name that differs from their registered name. Name matching
  will miss some of these, which is another reason "not found" is never an accusation.

## In plain English

We keep a slim copy of SEBI's list of registered advisers (names and numbers only, no phone
numbers or addresses) and check creators against it. If we can't find someone, we say exactly
that, and show you where to double-check on SEBI's website.

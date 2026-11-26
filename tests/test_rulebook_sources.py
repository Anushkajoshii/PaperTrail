from datetime import date, timedelta
from urllib.parse import urlparse

import pytest

from papertrail.models import OFFICIAL_SEBI_HOSTS, VerificationLevel
from papertrail.rulebook.sources import (
    REVERIFY_AFTER_DAYS,
    UnknownSourceError,
    get_source,
    get_sources,
    load_sources,
    stale_sources,
)

EXPECTED_IDS = {
    "sebi-ia-regs-2013",
    "sebi-ra-regs-2014",
    "sebi-circular-2025-11-association",
    "sebi-pr-22-2025-social-media",
    "sebi-pr-112-2016-registered-only",
    "sebi-investor-spot-a-scam",
    "sebi-pfutp-regs-2003",
}


def test_registry_loads_and_is_complete():
    assert set(load_sources()) == EXPECTED_IDS


@pytest.mark.parametrize("source_id", sorted(EXPECTED_IDS))
def test_every_source_is_official_dated_and_verified(source_id):
    s = get_source(source_id)
    assert urlparse(str(s.url)).hostname in OFFICIAL_SEBI_HOSTS
    assert s.summary and s.verified_on is not None
    # Anything not read in full must say how it was verified.
    if s.verification_level is not VerificationLevel.FULL_TEXT:
        assert s.verification_note


def test_key_facts_match_what_was_verified():
    ia, ra = get_source("sebi-ia-regs-2013"), get_source("sebi-ra-regs-2014")
    assert ia.published_on == date(2013, 1, 21) and ia.provisions[0].ref == "Regulation 3(1)"
    assert ra.published_on == date(2014, 9, 1) and ra.provisions[0].ref == "Regulation 3(1)"
    circ = get_source("sebi-circular-2025-11-association")
    assert circ.reference_number == "SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2025/11"
    assert circ.updated_on == date(2026, 5, 8)
    assert any("30 days" in p for p in circ.key_points)  # the May 2026 change, not "3 months"
    assert get_source("sebi-pr-22-2025-social-media").published_on == date(2025, 4, 11)
    assert get_source("sebi-investor-spot-a-scam").published_on is None  # page has no date


def test_unknown_source_is_an_error_not_a_guess():
    with pytest.raises(UnknownSourceError):
        get_source("sebi-made-up-rule-2099")
    assert [s.id for s in get_sources(["sebi-ia-regs-2013", "sebi-ia-regs-2013"])] == [
        "sebi-ia-regs-2013"
    ]


def test_staleness_check():
    assert stale_sources(date(2026, 11, 27)) == []
    later = date(2026, 11, 26) + timedelta(days=REVERIFY_AFTER_DAYS + 1)
    assert len(stale_sources(later)) == len(EXPECTED_IDS)


def test_generated_rulebook_doc_is_up_to_date():
    from pathlib import Path

    from papertrail.rulebook.catalog_doc import render

    doc = Path(__file__).parent.parent / "docs" / "SEBI_RULEBOOK.md"
    assert doc.read_text() == render(), "Run: make rulebook-docs"

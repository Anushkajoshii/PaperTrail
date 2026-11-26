import json
from datetime import date
from pathlib import Path

import pytest

from papertrail.models import RegistrationStatus
from papertrail.rulebook.registry import (
    Category,
    Registry,
    Snapshot,
    import_pages,
    lookup_registration,
    main,
    normalize_name,
    parse_register_html,
)

FIXTURE = (Path(__file__).parent / "fixtures" / "sebi_register_sample.html").read_text()
TODAY = date(2026, 11, 26)


@pytest.fixture
def registry():
    ra = parse_register_html(FIXTURE, Category.RESEARCH_ANALYST)
    return Registry(Snapshot(snapshot_date=date(2026, 11, 20), entries=ra))


def test_parser_keeps_only_safe_fields():
    entries = parse_register_html(FIXTURE, Category.RESEARCH_ANALYST)
    assert [e.registration_number for e in entries] == [
        "INH000000001",
        "INH000000002",
        "INA000000003",
    ]
    assert entries[0].valid_from == date(2022, 12, 22) and entries[0].valid_to is None
    assert entries[1].valid_to == date(2025, 1, 4)
    assert entries[2].name == "Rahul & Co Demo Advisory LLP"  # entities decoded
    dumped = json.dumps([e.model_dump(mode="json") for e in entries])
    for private in ("example", "0000000000", "Example Road", "contact"):
        assert private not in dumped


def test_normalize_name():
    assert normalize_name("DEMO WEALTH RESEARCH PRIVATE LIMITED") == "demo wealth research"
    assert normalize_name("Rahul & Co. Demo Advisory LLP") == "rahul demo advisory"


def test_lookup_by_registration_number_mentioned_in_text(registry):
    r = lookup_registration(
        registry, text="Main registered hoon, mera number inh000000001 hai", today=TODAY
    )
    assert r.status is RegistrationStatus.REGISTERED_RA
    assert r.match_basis == "registration_number"
    assert "does not mean SEBI endorses" in r.note


def test_lookup_by_name_variants(registry):
    full = lookup_registration(registry, name="Demo Wealth Research Pvt Ltd", today=TODAY)
    assert full.is_registered and full.match_basis == "name"
    assert "name only" in full.note
    # Proprietor's trade name inside brackets also matches, but that registration has expired.
    trade = lookup_registration(registry, name="Demo Market Insights", today=TODAY)
    assert (
        trade.status is RegistrationStatus.NOT_FOUND and "validity period has ended" in trade.note
    )


def test_not_found_wording_is_careful(registry):
    r = lookup_registration(registry, name="Totally Different Finfluencer", today=TODAY)
    assert r.status is RegistrationStatus.NOT_FOUND
    assert "not proof that the person is unregistered" in r.note
    assert "20 Nov 2026" in r.note
    unknown_no = lookup_registration(registry, text="My number is INH999999999", today=TODAY)
    assert unknown_no.status is RegistrationStatus.NOT_FOUND and "INH999999999" in unknown_no.note


def test_similar_but_different_names_do_not_match(registry):
    assert not lookup_registration(registry, name="Demo Wealth", today=TODAY).is_registered
    assert lookup_registration(registry, name="ab", today=TODAY).status is (
        RegistrationStatus.NOT_FOUND
    )


def test_no_registry_or_no_query_means_not_checked(registry):
    assert lookup_registration(None, name="x").status is RegistrationStatus.NOT_CHECKED
    assert lookup_registration(registry).status is RegistrationStatus.NOT_CHECKED


def test_import_and_cli(tmp_path, capsys):
    out = tmp_path / "snapshot.json"
    snap = import_pages([(FIXTURE, Category.RESEARCH_ANALYST)], out, snapshot_date=TODAY)
    assert len(snap.entries) == 3
    # Re-importing merges by registration number rather than duplicating.
    assert len(import_pages([(FIXTURE, Category.RESEARCH_ANALYST)], out).entries) == 3
    page = tmp_path / "page.html"
    page.write_text(FIXTURE)
    assert (
        main(["import", str(page), "--category", "investment_adviser", "--output", str(out)]) == 0
    )
    assert main(["lookup", "INA000000003", "--snapshot", str(out)]) == 0
    assert '"registered_investment_adviser"' in capsys.readouterr().out
    assert Registry.load(tmp_path / "missing.json") is None

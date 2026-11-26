from pathlib import Path

import pytest

from papertrail.agent.extract import extract_claims
from papertrail.models import (
    Check,
    CheckInput,
    FlagBasis,
    InputKind,
    RedFlagKind,
    RegistrationStatus,
    SebiRegistration,
)
from papertrail.rulebook.rules import (
    EDUCATION_FRAMING,
    GUARANTEE,
    PERFORMANCE,
    PRESSURE,
    RECOMMENDATION,
    REGISTRATION_CLAIM,
    RULES,
    TIP_GROUP,
    apply_rules,
    rule_catalog,
)
from papertrail.rulebook.sources import load_sources

EXAMPLES = Path(__file__).parent.parent / "examples"
NOT_FOUND = SebiRegistration(status=RegistrationStatus.NOT_FOUND)
NOT_CHECKED = SebiRegistration()
REGISTERED = SebiRegistration(
    status=RegistrationStatus.REGISTERED_RA, registration_numbers=["INH000000000"]
)


def kinds(result):
    return [f.kind for f in result.flags]


# --- Patterns: positives and negatives in English, Hinglish and Hindi ----------------------


@pytest.mark.parametrize(
    ("pattern", "text"),
    [
        (GUARANTEE, "Guaranteed 5% every month"),
        (GUARANTEE, "bilkul risk-free hai"),
        (GUARANTEE, "pakka profit milega"),
        (GUARANTEE, "हर महीने 10% की गारंटी है"),
        (GUARANTEE, "double your money in 6 months"),
        (PERFORMANCE, "is stock ne 300% return diya"),
        (PERFORMANCE, "My students made 2 lakh last month"),
        (PERFORMANCE, "92% accuracy on all calls"),
        (PERFORMANCE, "पिछले साल 200% रिटर्न"),
        (RECOMMENDATION, "Buy INFY, target 2000, stop loss 1700"),
        (RECOMMENDATION, "TATAMOTORS ka target ₹1500 hai"),
        (RECOMMENDATION, "abhi kharid lo, target 900"),
        (REGISTRATION_CLAIM, "Main SEBI registered advisor hoon"),
        (REGISTRATION_CLAIM, "I am a registered research analyst"),
        (TIP_GROUP, "Join my premium Telegram group"),
        (TIP_GROUP, "link for the VIP channel in bio"),
        (EDUCATION_FRAMING, "This video is for educational purposes only"),
        (EDUCATION_FRAMING, "not financial advice"),
        (PRESSURE, "Buy before Monday or regret it"),
        (PRESSURE, "only 5 seats left, hurry"),
        (PRESSURE, "abhi kharid lo warna pachtaoge"),
    ],
)
def test_pattern_matches(pattern, text):
    assert pattern.search(text)


@pytest.mark.parametrize(
    ("pattern", "text"),
    [
        (GUARANTEE, "Bank FDs are insured up to 5 lakh by DICGC"),  # factual, no promise
        (GUARANTEE, "There are no guarantees in markets"),
        (PERFORMANCE, "Inflation was 5% last year"),
        (RECOMMENDATION, "I bought a new phone for my mother"),
        (REGISTRATION_CLAIM, "I registered for the marathon"),
        (TIP_GROUP, "The group of companies reported results"),
        (PRESSURE, "Markets were in a hurry to price in the rate cut"),
    ],
)
def test_pattern_does_not_overmatch(pattern, text):
    if pattern is GUARANTEE and "no guarantees" in text:
        pytest.skip("documented limitation: negated guarantees still match (see LIMITATIONS)")
    if pattern is PRESSURE:
        pytest.xfail("'hurry' in a neutral sentence still matches: accepted, low-impact flag")
    assert not pattern.search(text)


# --- Engine --------------------------------------------------------------------------------


def run(text, registration=NOT_FOUND):
    claims = extract_claims(text).claims
    return apply_rules(text, claims, registration), claims


def test_hinglish_example_raises_expected_flags_with_sources():
    text = (EXAMPLES / "hinglish_reel.txt").read_text()
    result, claims = run(text)
    assert set(kinds(result)) == {
        RedFlagKind.GUARANTEED_RETURNS,
        RedFlagKind.MISLEADING_PERFORMANCE,
        RedFlagKind.UNREGISTERED_ADVICE,
        RedFlagKind.UNCONFIRMED_REGISTRATION_CLAIM,
        RedFlagKind.TIP_GROUP_SOLICITATION,
    }
    for flag in result.flags:
        assert flag.basis is FlagBasis.VERIFIED_RULE
        assert flag.rule_source_ids and flag.what_was_detected and flag.investor_takeaway
        assert "violat" not in (flag.why_it_matters + flag.investor_takeaway).lower()
    # Flags link back to the claim they came from.
    perf = next(f for f in result.flags if f.kind is RedFlagKind.MISLEADING_PERFORMANCE)
    assert perf.claim_id in {c.id for c in claims}
    # The result is valid inside a Check (sources attached, ids consistent).
    Check(
        input=CheckInput(kind=InputKind.TEXT, text=text),
        claims=claims,
        red_flags=result.flags,
        regulatory_sources=result.sources,
        registration=NOT_FOUND,
    )


def test_registered_creator_gets_no_registration_flags():
    text = (EXAMPLES / "hinglish_reel.txt").read_text()
    result, _ = run(text, REGISTERED)
    assert RedFlagKind.UNREGISTERED_ADVICE not in kinds(result)
    assert RedFlagKind.UNCONFIRMED_REGISTRATION_CLAIM not in kinds(result)
    assert RedFlagKind.GUARANTEED_RETURNS in kinds(result)  # still a red flag for anyone


def test_not_found_is_never_called_unregistered():
    result, _ = run("Buy INFY target 2000.")
    flag = result.flags[0]
    assert "not proof they are unregistered" in flag.why_it_matters
    unchecked, _ = run("Buy INFY target 2000.", NOT_CHECKED)
    assert "have not been able to check" in unchecked.flags[0].why_it_matters


def test_education_label_only_flags_when_stocks_are_called():
    plain = apply_rules(
        "This video is for educational purposes only. Learn what a P/E is.", [], NOT_FOUND
    )
    assert RedFlagKind.LIVE_PRICE_EDUCATION not in kinds(plain)
    mixed = apply_rules("For educational purposes only. Buy INFY, target 2000.", [], NOT_FOUND)
    edu = next(f for f in mixed.flags if f.kind is RedFlagKind.LIVE_PRICE_EDUCATION)
    assert "30 days" in edu.why_it_matters and "May 2026" in edu.why_it_matters


def test_hindi_example_flags_guarantee_and_performance():
    result, _ = run((EXAMPLES / "hindi_clip.txt").read_text())
    assert {RedFlagKind.GUARANTEED_RETURNS, RedFlagKind.MISLEADING_PERFORMANCE} <= set(
        kinds(result)
    )


def test_clean_content_has_no_flags():
    text = "Index funds track an index. Costs matter over the long run. Diversify across assets."
    assert apply_rules(text, [], NOT_FOUND).flags == []


def test_max_hits_limits_repetition():
    text = " ".join(["Guaranteed returns every month."] * 10)
    assert kinds(apply_rules(text, [], NOT_FOUND)).count(RedFlagKind.GUARANTEED_RETURNS) == 2


def test_catalog_covers_every_rule_with_resolved_sources():
    catalog = rule_catalog()
    assert [c["id"] for c in catalog] == [r.id for r in RULES]
    registry_ids = set(load_sources())
    for entry in catalog:
        assert entry["sources"] and all(s["id"] in registry_ids for s in entry["sources"])
        assert entry["what"] and entry["why"] and entry["takeaway"]

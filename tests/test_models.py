from datetime import date

import pytest
from pydantic import ValidationError

from papertrail.models import (
    STANDARD_NOTICES,
    Check,
    CheckInput,
    CheckStatus,
    Claim,
    ClaimType,
    ConfidenceBand,
    Evidence,
    Explanation,
    FlagBasis,
    InputKind,
    RedFlag,
    RedFlagKind,
    RegistrationStatus,
    RegulatorySource,
    SebiDocType,
    SebiRegistration,
    SourceQuality,
    SourceType,
    Stance,
    Verdict,
    VerdictLabel,
)


def make_claim(**kw) -> Claim:
    defaults = dict(
        id="clm_1",
        text="Stock X returned 300% in 2023.",
        quote="X ne 2023 mein 300% diya",
        claim_type=ClaimType.PAST_PERFORMANCE,
    )
    return Claim(**(defaults | kw))


def make_evidence(stance=Stance.CONTRADICTS, **kw) -> Evidence:
    defaults = dict(
        id="evd_1",
        claim_id="clm_1",
        url="https://www.nseindia.com/some-report",
        title="NSE annual data",
        source_type=SourceType.EXCHANGE,
        snippet="Stock X rose 42% in calendar year 2023.",
        stance=stance,
        quality=SourceQuality(reliability=0.95, recency=0.8, relevance=0.9),
    )
    return Evidence(**(defaults | kw))


def make_verdict(**kw) -> Verdict:
    defaults = dict(
        claim_id="clm_1",
        label=VerdictLabel.CONTRADICTED,
        confidence=0.82,
        explanation=Explanation(summary="Exchange data shows 42%, not 300%."),
        contradicting_evidence_ids=["evd_1"],
    )
    return Verdict(**(defaults | kw))


def make_source(**kw) -> RegulatorySource:
    defaults = dict(
        id="sebi-ia-regs",
        title="SEBI (Investment Advisers) Regulations, 2013",
        doc_type=SebiDocType.REGULATION,
        url="https://www.sebi.gov.in/legal/regulations/example.html",
        published_on=date(2013, 1, 21),
        summary="Rules for who can give paid investment advice.",
    )
    return RegulatorySource(**(defaults | kw))


def text_input() -> CheckInput:
    return CheckInput(kind=InputKind.TEXT, text="Guaranteed 5% monthly returns!")


# --- Claims and evidence -----------------------------------------------------------------


def test_claim_gets_generated_id():
    c = Claim(text="Nifty hit 26k", quote="Nifty 26k", claim_type=ClaimType.MARKET_FACT)
    assert c.id.startswith("clm_")


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        make_claim(made_up_field=1)


def test_source_quality_bounds_and_overall():
    q = SourceQuality(reliability=1, recency=1, relevance=1)
    assert q.overall == 1.0
    with pytest.raises(ValidationError):
        SourceQuality(reliability=1.2, recency=0, relevance=0)


# --- Verdicts ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("confidence", "band"),
    [
        (0.9, ConfidenceBand.HIGH),
        (0.75, ConfidenceBand.HIGH),
        (0.5, ConfidenceBand.MEDIUM),
        (0.2, ConfidenceBand.LOW),
    ],
)
def test_confidence_band(confidence, band):
    assert make_verdict(confidence=confidence).confidence_band is band


def test_supported_requires_supporting_evidence():
    with pytest.raises(ValidationError, match="supporting"):
        make_verdict(label=VerdictLabel.SUPPORTED, contradicting_evidence_ids=[])


def test_contradicted_requires_contradicting_evidence():
    with pytest.raises(ValidationError, match="contradicting"):
        make_verdict(contradicting_evidence_ids=[])


def test_misleading_requires_some_evidence():
    with pytest.raises(ValidationError, match="misleading"):
        make_verdict(label=VerdictLabel.MISLEADING, contradicting_evidence_ids=[])


def test_not_verifiable_allows_no_evidence():
    v = make_verdict(
        label=VerdictLabel.NOT_VERIFIABLE,
        confidence=0.3,
        contradicting_evidence_ids=[],
        explanation=Explanation(
            summary="No public record found.", could_not_verify=["Private Telegram results"]
        ),
    )
    assert v.description.startswith("We could not find")


# --- Regulatory sources and red flags ----------------------------------------------------


def test_regulatory_source_must_be_on_sebi_domain():
    with pytest.raises(ValidationError, match=r"sebi\.gov\.in"):
        make_source(url="https://random-blog.com/sebi-rules")


def test_regulatory_source_dates_are_sane():
    with pytest.raises(ValidationError, match="effective_from"):
        make_source(published_on=date(2024, 8, 29), effective_from=date(2024, 1, 1))


def test_verified_rule_flag_requires_source():
    with pytest.raises(ValidationError, match="official SEBI source"):
        RedFlag(
            kind=RedFlagKind.GUARANTEED_RETURNS,
            basis=FlagBasis.VERIFIED_RULE,
            detected_text="guaranteed 5% monthly",
            what_was_detected="A promise of fixed returns.",
            why_it_matters="Market investments cannot guarantee returns.",
            investor_takeaway="Treat guaranteed-return promises with caution.",
        )


def test_potential_concern_cannot_cite_a_provision():
    with pytest.raises(ValidationError, match="provision"):
        RedFlag(
            kind=RedFlagKind.OTHER,
            basis=FlagBasis.POTENTIAL_CONCERN,
            detected_text="join my VIP group",
            what_was_detected="An invitation to a paid group.",
            why_it_matters="May involve paid tips.",
            investor_takeaway="Check registration first.",
            relevant_provision="Regulation 99(z)",  # invented provisions must be impossible
        )


def test_registration_default_note_explains_no_endorsement():
    reg = SebiRegistration(status=RegistrationStatus.REGISTERED_RA)
    assert reg.is_registered
    assert "does not" in reg.note
    assert not SebiRegistration(status=RegistrationStatus.NOT_FOUND).is_registered


# --- Check-level consistency -------------------------------------------------------------


def test_input_payload_must_match_kind():
    with pytest.raises(ValidationError, match="requires 'url'"):
        CheckInput(kind=InputKind.ARTICLE_URL)
    with pytest.raises(ValidationError, match="requires 'upload_key'"):
        CheckInput(kind=InputKind.VIDEO)


def test_full_check_is_valid_and_carries_notices():
    flag = RedFlag(
        kind=RedFlagKind.GUARANTEED_RETURNS,
        basis=FlagBasis.VERIFIED_RULE,
        detected_text="guaranteed 300%",
        claim_id="clm_1",
        what_was_detected="A promise of guaranteed returns.",
        why_it_matters="Securities markets carry risk; returns cannot be guaranteed.",
        investor_takeaway="Be cautious of anyone promising fixed returns.",
        rule_source_ids=["sebi-ia-regs"],
    )
    check = Check(
        input=text_input(),
        status=CheckStatus.COMPLETED,
        claims=[make_claim()],
        evidence=[make_evidence()],
        verdicts=[make_verdict()],
        red_flags=[flag],
        regulatory_sources=[make_source()],
    )
    assert check.notices == STANDARD_NOTICES
    assert check.verdict_for("clm_1").label is VerdictLabel.CONTRADICTED
    assert len(check.evidence_for("clm_1")) == 1
    assert check.status_description.startswith("Done")
    # Round-trips through JSON (what the API and DynamoDB will store).
    assert Check.model_validate_json(check.model_dump_json()) == check


def test_verdict_cannot_cite_evidence_with_wrong_stance():
    with pytest.raises(ValidationError, match="stance"):
        Check(
            input=text_input(),
            claims=[make_claim()],
            evidence=[make_evidence(stance=Stance.SUPPORTS)],
            verdicts=[make_verdict()],  # cites evd_1 as contradicting
        )


def test_verdict_cannot_cite_missing_evidence():
    with pytest.raises(ValidationError, match="unknown evidence"):
        Check(input=text_input(), claims=[make_claim()], verdicts=[make_verdict()])


def test_red_flag_cannot_cite_unattached_source():
    flag = RedFlag(
        kind=RedFlagKind.GUARANTEED_RETURNS,
        basis=FlagBasis.VERIFIED_RULE,
        detected_text="guaranteed",
        what_was_detected="x",
        why_it_matters="y",
        investor_takeaway="z",
        rule_source_ids=["sebi-invented-rule"],
    )
    with pytest.raises(ValidationError, match="not attached"):
        Check(input=text_input(), red_flags=[flag])


def test_failed_check_needs_error():
    with pytest.raises(ValidationError, match="error"):
        Check(input=text_input(), status=CheckStatus.FAILED)

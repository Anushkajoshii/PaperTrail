from datetime import date

from papertrail.api.creators import MIN_SAMPLE, build_profile, ledger_summary, track_record
from papertrail.ledger.models import LedgerEntry, LedgerStatus
from papertrail.models import (
    Check,
    CheckInput,
    CheckStatus,
    Claim,
    ClaimType,
    Explanation,
    InputKind,
    Verdict,
    VerdictLabel,
)


def check(labels, status=CheckStatus.COMPLETED):
    claims = [
        Claim(
            id=f"clm_{i}",
            text="Nifty gave 12%",
            quote="Nifty 12%",
            claim_type=ClaimType.MARKET_FACT,
        )
        for i in range(len(labels))
    ]
    verdicts = [
        Verdict(
            claim_id=c.id,
            label=label,
            confidence=0.3,
            explanation=Explanation(summary="s"),
        )
        for c, label in zip(claims, labels, strict=True)
        if label is VerdictLabel.NOT_VERIFIABLE
    ]
    return Check(
        input=CheckInput(kind=InputKind.TEXT, text="x y z", creator_handle="@d"),
        status=status,
        claims=claims,
        verdicts=verdicts,
    )


def test_shares_only_with_enough_assessed_claims():
    small = track_record([check([VerdictLabel.NOT_VERIFIABLE] * 3)])
    assert small.assessed == 0 and small.supported_share is None and not small.enough_data


def entry(i, status):
    return LedgerEntry(
        id=f"led_{i}",
        check_id="chk",
        claim_id=f"clm_{i}",
        ticker="KESTREL",
        claim_text="t",
        quote="q",
        target_price=100.0,
        made_on=date(2026, 7, i + 1),
        due_on=date(2026, 12, 31),
        deadline_stated=True,
        status=status,
    )


def test_ledger_hit_share_needs_enough_settled_calls():
    few = ledger_summary([entry(0, LedgerStatus.HIT), entry(1, LedgerStatus.OPEN)])
    assert few.settled == 1 and few.hit_share is None and few.counts["open"] == 1
    many = [entry(i, LedgerStatus.HIT if i < 2 else LedgerStatus.MISSED) for i in range(MIN_SAMPLE)]
    s = ledger_summary(many)
    assert s.settled == MIN_SAMPLE and s.hit_share == round(2 / MIN_SAMPLE, 3)


def test_profiles_ignore_unfinished_checks():
    assert build_profile("d", [check([], status=CheckStatus.RESEARCHING)], []) is None

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from papertrail.config import Settings
from papertrail.ledger.models import Direction, LedgerEntry, LedgerStatus
from papertrail.ledger.parse import (
    DEFAULT_HORIZON_DAYS,
    parse_deadline,
    parse_prediction,
    parse_target_price,
)
from papertrail.ledger.prices import (
    AlphaVantagePrices,
    NoPrices,
    OfflinePrices,
    PriceError,
    PricePoint,
    get_price_provider,
)
from papertrail.ledger.service import entry_id, run_daily, track_check
from papertrail.ledger.settle import settle
from papertrail.ledger.store import MemoryLedgerStore, SqliteLedgerStore
from papertrail.models import Check, CheckInput, CheckStatus, Claim, ClaimType, InputKind

TODAY = date(2026, 11, 27)


def call(quote, text=None, tickers=("KESTREL",), kind=ClaimType.STOCK_CALL):
    return Claim(text=text or quote, quote=quote, claim_type=kind, tickers=list(tickers))


# -- parsing ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected", "stated"),
    [
        ("March tak pakka jayega", date(2027, 3, 31), True),
        ("by December", date(2026, 12, 31), True),  # same year: month not over yet
        ("November tak", date(2026, 11, 30), True),
        ("by March 2028", date(2028, 3, 31), True),
        ("Mar '27 tak", date(2027, 3, 31), True),
        ("मार्च तक", date(2027, 3, 31), True),
        ("in 3 months", date(2027, 2, 27), True),
        ("6 mahine mein", date(2027, 5, 27), True),
        ("2 hafte mein", date(2026, 12, 11), True),
        ("is saal", date(2026, 12, 31), True),
        ("agle saal tak", date(2027, 12, 31), True),
        ("soon", TODAY + timedelta(days=DEFAULT_HORIZON_DAYS), False),
    ],
)
def test_deadlines(text, expected, stated):
    assert parse_deadline(text, TODAY) == (expected, stated)


@pytest.mark.parametrize(
    ("text", "target"),
    [
        ("TATAMOTORS ka target ₹1500 hai", 1500),
        ("Buy ORIONBANK with a target of ₹950 and stop loss ₹780", 950),
        ("stop loss Rs 780, target Rs 950", 950),
        ("it will cross ₹1,250 in 2027", 1250),
        ("2027 mein 300% dega", None),  # years and percentages are not prices
    ],
)
def test_target_prices(text, target):
    assert parse_target_price(text) == target


def test_predictions_from_claims():
    p = parse_prediction(call("XYZ 3 mahine mein ₹200 tak girega", tickers=["xyz"]), TODAY)
    assert (p.ticker, p.direction, p.target_price) == ("XYZ", Direction.DOWN, 200)
    p = parse_prediction(call("Lotus Foods is saal 50% dega", tickers=["LOTUSFOOD"]), TODAY)
    assert (p.target_price, p.target_pct, p.due_on) == (None, 50, date(2026, 12, 31))
    # Not trackable: no symbol, not a stock call, no target, or a business (not price) forecast
    assert parse_prediction(call("target ₹1500 by March", tickers=()), TODAY) is None
    assert parse_prediction(call("Nifty hit ₹1500", kind=ClaimType.MARKET_FACT), TODAY) is None
    assert parse_prediction(call("Kestrel will go up a lot"), TODAY) is None
    assert parse_prediction(call("Kestrel Q1 profit will jump 50%"), TODAY) is None


# -- settling --------------------------------------------------------------------------------


def entry(**kw):
    base = dict(
        id="led_1",
        check_id="chk_1",
        claim_id="clm_1",
        ticker="KESTREL",
        claim_text="Kestrel will reach ₹110 by 31 Jan.",
        quote="Kestrel ₹110 tak",
        target_price=110.0,
        made_on=date(2027, 1, 1),
        due_on=date(2027, 1, 31),
        deadline_stated=True,
    )
    return LedgerEntry(**(base | kw))


def series(*rows):
    start = date(2027, 1, 1)
    return [
        PricePoint(start + timedelta(days=i), high, low, close)
        for i, (high, low, close) in enumerate(rows)
    ]


def flat(n, price=100.0):
    return [(price + 1, price - 1, price)] * n


def test_hit_when_the_high_reaches_the_target_before_the_deadline():
    e = settle(entry(), series(*flat(5), (111, 99, 105), *flat(30)), date(2027, 2, 5), "test")
    assert e.status is LedgerStatus.HIT and e.hit_on == date(2027, 1, 6)
    assert e.baseline_price == 100 and e.best_price == 111 and "Reached ₹110.00" in e.note


def test_reaching_the_target_after_the_deadline_does_not_count():
    points = series(*flat(31), (120, 100, 115))  # day 32 = 1 Feb, after the deadline
    e = settle(entry(), points, date(2027, 2, 5), "test")
    assert e.status is LedgerStatus.MISSED and e.best_price == 101
    assert "closest: ₹101.00" in e.note


def test_open_until_the_deadline_and_open_if_prices_stop_early():
    assert settle(entry(), series(*flat(10)), date(2027, 1, 11), "t").status is LedgerStatus.OPEN
    # Deadline passed but prices end weeks before it: not enough to call it missed.
    assert settle(entry(), series(*flat(10)), date(2027, 3, 1), "t").status is LedgerStatus.OPEN


def test_falling_calls_and_percentage_targets():
    down = entry(target_price=90.0)  # below the starting price: a call that it will fall
    e = settle(down, series(*flat(3), (95, 89, 90)), date(2027, 1, 5), "t")
    assert e.direction is Direction.DOWN and e.status is LedgerStatus.HIT
    pct = entry(target_price=None, target_pct=20.0)
    e = settle(pct, series(*flat(3), (121, 110, 119)), date(2027, 1, 5), "t")
    assert e.resolved_target() == 120 and e.status is LedgerStatus.HIT


def test_no_prices_means_no_data_and_settled_entries_never_change():
    e = settle(entry(), [], date(2027, 1, 5), "t")
    assert e.status is LedgerStatus.NO_DATA and "No price data" in e.note
    done = entry(status=LedgerStatus.HIT)
    assert settle(done, series(*flat(40)), date(2027, 3, 1), "t") is done


# -- prices ----------------------------------------------------------------------------------


def test_offline_prices_only_know_fictional_symbols():
    prices = OfflinePrices()
    assert prices.daily("KESTREL", date(2026, 7, 1))[0].day >= date(2026, 7, 1)
    assert prices.daily("TATAMOTORS", date(2026, 7, 1)) == []
    assert NoPrices().daily("KESTREL", date(2026, 7, 1)) == []


def av_client(body):
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))


def test_alphavantage_parses_daily_prices_and_errors():
    body = {
        "Time Series (Daily)": {
            "2027-01-05": {"2. high": "105", "3. low": "99", "4. close": "104"},
            "2027-01-04": {"2. high": "101", "3. low": "98", "4. close": "100"},
            "2026-12-31": {"2. high": "90", "3. low": "89", "4. close": "90"},
        }
    }
    pts = AlphaVantagePrices("k", av_client(body)).daily("orionbank", date(2027, 1, 1))
    assert [p.day.day for p in pts] == [4, 5] and pts[-1].close == 104
    unknown = AlphaVantagePrices("k", av_client({"Error Message": "Invalid API call"}))
    assert unknown.daily("NOPE", date(2027, 1, 1)) == []
    with pytest.raises(PriceError, match="25 requests"):
        AlphaVantagePrices("k", av_client({"Information": "limit is 25 requests per day"})).daily(
            "X", date(2027, 1, 1)
        )


def test_price_provider_selection():
    assert isinstance(get_price_provider(Settings(_env_file=None)), NoPrices)
    assert isinstance(
        get_price_provider(Settings(_env_file=None, price_provider="offline")), OfflinePrices
    )
    no_key = Settings(_env_file=None, price_provider="alphavantage")
    assert isinstance(get_price_provider(no_key), NoPrices)
    keyed = Settings(_env_file=None, price_provider="alphavantage", alphavantage_api_key="k")
    assert isinstance(get_price_provider(keyed), AlphaVantagePrices)


# -- stores and the daily job ---------------------------------------------------------------


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    return (
        MemoryLedgerStore() if request.param == "memory" else SqliteLedgerStore(tmp_path / "l.db")
    )


def check_with(*claims, handle="@Demo"):
    return Check(
        input=CheckInput(kind=InputKind.TEXT, text="x y z", creator_handle=handle),
        status=CheckStatus.COMPLETED,
        claims=list(claims),
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
    )


def test_track_check_adds_each_call_once(store):
    c = check_with(
        call("Kestrel ₹1500 tak jayega March 2027 tak"),
        call("Orion ₹950 target", tickers=["ORIONBANK"]),
        call("Kestrel gave 40% last year", kind=ClaimType.PAST_PERFORMANCE),
    )
    added = track_check(c, store)
    assert {e.ticker for e in added} == {"KESTREL", "ORIONBANK"}
    assert all(e.creator == "demo" and e.made_on == date(2026, 7, 1) for e in added)
    assert track_check(c, store) == []  # at-least-once delivery: no duplicates
    assert store.get(entry_id(c.claims[0].id)).due_on == date(2027, 3, 31)
    assert [e.ticker for e in store.list_by_creator("demo")]
    assert track_check(c.model_copy(update={"status": CheckStatus.FAILED}), store) == []


def test_daily_job_settles_calls_with_demo_prices(store):
    c = check_with(
        call("Kestrel March 2027 tak ₹1500 jayega"),  # demo series reaches it
        call("Orion target ₹950 by January 2027", tickers=["ORIONBANK"]),  # peaks below it
        call("TATAMOTORS ka target ₹1500", tickers=["TATAMOTORS"]),  # real symbol: no demo data
    )
    track_check(c, store)
    summary = run_daily(store, OfflinePrices(), date(2027, 6, 30))
    by_ticker = {e.ticker: e for e in store.list_recent()}
    assert by_ticker["KESTREL"].status is LedgerStatus.HIT
    assert by_ticker["ORIONBANK"].status is LedgerStatus.MISSED
    assert by_ticker["TATAMOTORS"].status is LedgerStatus.NO_DATA
    assert summary["tickers"] == 3 and summary["hit"] == 1 and summary["missed"] == 1
    assert {e.ticker for e in store.list_active()} == {"TATAMOTORS"}


def test_daily_job_rations_price_requests_and_survives_errors(store):
    class Failing:
        source = "x"

        def daily(self, ticker, since):
            raise PriceError("limit")

    for i, t in enumerate(["AAA", "BBB", "CCC"]):
        store.save(entry(id=f"led_{i}", ticker=t))
    assert run_daily(store, Failing(), date(2027, 1, 5), max_tickers=2) == {
        "price_errors": 2,
        "tickers": 2,
        "skipped_tickers": 1,
    }


def test_calls_without_data_are_given_up_30_days_after_their_deadline(store):
    store.save(entry(id="led_old", ticker="OLD", status=LedgerStatus.NO_DATA))  # due 31 Jan
    assert run_daily(store, NoPrices(), date(2027, 2, 20))["tickers"] == 1  # still retried
    assert run_daily(store, NoPrices(), date(2027, 3, 5))["tickers"] == 0  # given up

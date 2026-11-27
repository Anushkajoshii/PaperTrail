# The Claim Ledger and creator profiles

## Why

A stock call such as *"TATAMOTORS ka target ₹1500 hai, March tak pakka jayega"* can't be
fact-checked on the day it is made. It is a prediction. The honest verdict that day is "not
verifiable yet". The Claim Ledger keeps the call and settles it later against real prices, so a
creator's track record is built from what actually happened, not from what they say about
themselves.

## How a call is tracked

1. When a check finishes, every **stock call** that has a symbol and a target is added to the
   ledger. Running the same check twice never adds a duplicate.
2. The **symbol, target and deadline are read from the creator's own words** by deterministic
   code (`papertrail/ledger/parse.py`), never by an AI. This works for English, Hinglish and
   Devanagari month names:

   | Said | Tracked as |
   |---|---|
   | "TATAMOTORS ka target ₹1500 hai, March tak" | up to ₹1,500 by 31 March |
   | "Buy ORIONBANK, target ₹950, stop loss ₹780" | up to ₹950 (the stop loss is ignored), 90 days |
   | "XYZ 3 mahine mein ₹200 tak girega" | down to ₹200 within 3 months |
   | "LOTUSFOOD is saal 50% dega" | up 50% from the starting price by 31 December |
   | "Kestrel's profit will jump 50%" | not tracked: a business forecast, not a share price |

3. With no deadline, **90 days** are used, and the call is marked "no deadline given".
4. **Tracking starts when PaperTrail first saw the call.** The original post may be older, and
   the site says so.

## How a call is settled

Every weekday at 17:00 IST, after the market closes, the daily job re-checks open calls:

| Status | Rule |
|---|---|
| **Target reached** | On some day between the start of tracking and the deadline, the day's **high** reached the target (the day's **low**, for a call that the price will fall). |
| **Target missed** | The deadline has passed, prices cover the whole period, and the target was never reached. |
| **Still running** | Neither yet. |
| **No price data** | No prices for the symbol. Retried until 30 days after the deadline. |

Only prices dated between the start of tracking and today count. A target below the starting
price is treated as a call that the price will fall.

## Prices

| `PAPERTRAIL_PRICE_PROVIDER` | Source |
|---|---|
| `none` (default) | No prices. Calls stay open and are never settled with made-up data. |
| `offline` | Demo prices for **fictional** symbols only (KESTREL, ORIONBANK, LOTUSFOOD), for tests and demos. Real companies never get fake numbers. |
| `alphavantage` | Alpha Vantage daily prices for BSE listings: a free key, 25 requests a day, no card. |

Each symbol is fetched once per run and at most 20 symbols are fetched per day, which keeps the
job inside the free quota. Alpha Vantage's free daily series covers about the last 100 trading
days, so a call whose tracking started earlier than that stays open rather than being guessed.

**Turn on real prices (free):**
1. Get a key at https://www.alphavantage.co/support/#api-key.
2. Add `PAPERTRAIL_ALPHAVANTAGE_API_KEY=...` to `.env`.
3. Copy it to AWS with `AWS_PROFILE=portfolio uv run python scripts/push_secrets.py`.

## Creator profiles and comparison

`/creators/{handle}` and the creator page show:
- **Track record of checked claims:** counts by verdict. The share supported is shown only once
  at least **5** claims could be assessed. A few checks can't describe a whole channel.
- **Claim Ledger:** every call, with its starting price, the closest the price came, and the
  outcome. The hit rate is shown only once at least 5 calls are settled.
- **Red-flag timeline:** official SEBI flags and AI potential concerns, newest first, each
  linked to its check.
- **SEBI registration** from the latest check.

`/compare` puts two or three creators side by side, under a note that this is **not a
recommendation** and that creators with different numbers of checks aren't directly
comparable.

There is deliberately **no single "accountability score"**. See
[ADR-018](adr/018-ledger-and-profiles-without-a-score.md).

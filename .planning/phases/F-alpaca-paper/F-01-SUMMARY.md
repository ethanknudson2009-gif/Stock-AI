# Phase F — Alpaca Paper Adapter — Plan 01 SUMMARY

**Completed:** 2026-10-13
**Requirements satisfied:** AP-01, AP-02, AP-03, AP-04, AP-05, AP-06

## What shipped
- `stock_ai/execution/paper.py` — `AlpacaPaperBroker` conforms to the Broker Protocol (AP-02); the ONLY module importing alpaca-py (AP-01). Constructor builds `TradingClient(..., paper=True)` from `.env` keys or takes an injected client, and **hard-asserts `paper-api.alpaca.markets`** is the base URL — refuses to run against live (AP-03, Pitfall #1). `submit_order` pre-flights `get_asset().tradable` (AP-06), picks exactly one of notional/qty, passes `client_order_id` for idempotency, and treats Alpaca's duplicate-id rejection as success (AP-04, Pitfall #2).
- `stock_ai/execution/clock.py` — `now_eastern()` / `trading_day_today(now=None)` via `zoneinfo.ZoneInfo("America/New_York")`; a PT clock at 11:59pm yields the correct Eastern date (AP-05, Pitfall #7).
- `stock_ai/execution/base.py` — `Order` gains optional `notional` / `qty` (backward-compatible; FakeBroker and diff ignore them).
- `requirements.txt` — `alpaca-py>=0.43,<0.50` (installed 0.44.0). `.env.example` documents DRY_RUN.

## Tests
`tests/test_paper_broker.py` (8, all offline via a FakeTradingClient — no network/keys):
Protocol conformance, **test_paper_endpoint_assertion** (RH-01 #1), **test_idempotent_submission** (RH-01 #2), pre-flight rejects non-tradable, submit requires size, positions/account mapping, **test_trading_day_timezone** (RH-01 #5), and `paper.py` is the sole alpaca importer. **49 passed total.**

## Deviations / notes
- Live paper trading is a **human checkpoint**: it needs real Alpaca paper keys in `.env`. All safety contracts are proven offline with a mock client; no live call is made in tests.
- `AlpacaPaperBroker` is imported from `stock_ai.execution.paper` directly (not re-exported from the package `__init__`) so importing `FakeBroker` never pulls in alpaca-py.

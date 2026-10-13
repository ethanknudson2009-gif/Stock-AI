# Phase E — Broker Protocol + FakeBroker — Plan 01 SUMMARY

**Completed:** 2026-10-13
**Requirements satisfied:** BR-01, BR-02, BR-03, BR-04

## What shipped
- `stock_ai/execution/base.py` — `Broker` Protocol (`get_account`, `get_positions`, `submit_order`, `cancel_order`); `Order` frozen dataclass; `make_client_order_id(day, ticker, side)` → deterministic `YYYY-MM-DD_TICKER_side` (BR-01, Pitfall #2).
- `stock_ai/execution/diff.py` — pure `diff(current_positions, target_tickers, trading_day, max_positions=None)`: emits sorted sells (held − target) then buys (target − held); cap truncates target to first N (BR-03).
- `stock_ai/execution/fake.py` — `FakeBroker`: in-memory, deterministic; idempotent on `client_order_id`; `dry_run` (explicit or from `DRY_RUN` env) logs a no-op and changes no state (BR-02, BR-04).
- `stock_ai/execution/__init__.py` — package docstring notes: no SDK here; Alpaca lands only in future `paper.py`.

## Tests
`tests/test_execution.py` (11): Protocol conformance, deterministic client_order_id, diff empty→full / full→empty / partial rotation, **order cap enforced** (RH-01 #9), deterministic sorted output, submit records + updates positions, **idempotent duplicate submission** (Pitfall #2), **dry-run short-circuit** (RH-01 #10), DRY_RUN read from env. **39 passed total.**

Verified: `grep -rn alpaca stock_ai/execution/` is clean (success criterion 4). Single-ticker CLI output unchanged.

## Deviations
- `diff` takes an explicit `trading_day` argument rather than computing "today", so order ids stay pure/testable and the US/Eastern date decision is deferred to the Phase G caller (Pitfall #7).
- `FakeBroker` models long/flat as qty 1.0 / absent (v1 is equal-weight long/flat); share-quantity sizing is out of scope until it's needed.

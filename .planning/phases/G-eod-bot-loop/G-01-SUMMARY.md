# Phase G — EOD Bot Loop — Plan 01 SUMMARY

**Completed:** 2026-10-13
**Requirements satisfied:** BL-01, BL-02, BL-03, BL-04, BL-05, BL-06, BL-07

## What shipped
- `bot.py` (repo root) — PURE at import (only defs/constants; Pitfall #20). `run_eod(broker, ...)` = plan → enforce caps → submit (BL-01). `plan_orders` trains per-ticker, ranks top-N, diffs vs current positions, sizes buys by dollars / sells by held qty. `latest_signals` gets each ticker's latest P(up).
- Safety rails: `dry_run_enabled()` defaults ON unless DRY_RUN explicitly false (BL-05); `kill_switch_active()` halts on a `KILL_SWITCH` file at repo root (BL-04); `enforce_caps()` raises (never truncates) on `MAX_ORDERS_PER_DAY=20` (BL-03) or `MAX_ORDER_USD=500` (BL-02). Orders logged to `logs/orders.csv`.
- `app.py` — "Paper trade (preview)" mode: Preview orders → table → **Confirm & submit** (BL-06). Submits exactly the stashed `st.session_state["pending_orders"]` (Pitfall #16). Falls back to a demo FakeBroker when no Alpaca keys, and surfaces DRY_RUN state.
- `.gitignore` adds `KILL_SWITCH`, `logs/`. `requirements.txt` adds pytest + pytest-socket.

## Tests
- `tests/test_bot_import.py::test_bot_import_no_network` — sockets disabled; `import bot` makes zero network calls (RH-01 #7 / BL-07).
- `tests/test_bot_logic.py` (7) — DRY_RUN default on/off, cap rejections (count + $), dry-run logs-not-submits, kill-switch halt, live-path submits + idempotent on resubmit.
- **57 passed total.**

Verified live (DRY_RUN): `plan_orders(['AAPL','MSFT','NVDA'], top_n=2)` → buys AAPL+NVDA, logged to logs/orders.csv, 0 submitted.

## Deviations / notes
- Live paper submission is a human checkpoint (needs real Alpaca keys + `DRY_RUN=false`). Everything is proven offline with FakeBroker.
- Scheduling (cron/launchd) is out of scope for this phase; `run_eod` is the entry point a scheduler would call.

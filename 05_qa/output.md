# 05 · QA — Output

## Current coverage (28 tests passing, 2026-10-13)
- `test_indicators`, `test_classifier`, `test_signal` — feature/label/signal invariants.
- `test_backtest` — costs reduce return, zero-trade = zero cost, max drawdown math.
- `test_rf_backend` — Protocol conformance + aligned output.
- `test_cli_regression` — single-ticker CLI output stays byte-identical (Phase A baseline).
- `test_config` — secret redaction/scrub, single `load_dotenv`, universe shape, `.env.example`.
- `test_multi_engine` — top-N weighting, no-NaN portfolio, **portfolio Sharpe ≠ avg of
  per-ticker Sharpes** (Pitfall #3), Sharpe≈0 on random signals, calendar alignment.

## Anti-regression floor (must never go red)
No train/test leakage · cost reduces returns · CLI byte-identical · secrets never printed ·
portfolio Sharpe computed on the combined series.

## Manual / UAT (not unit-tested)
- `streamlit run app.py` renders both modes and redacts errors (no key in traceback).
- Phase F+: Alpaca paper orders hit the PAPER endpoint only; DRY_RUN default; idempotent re-run.

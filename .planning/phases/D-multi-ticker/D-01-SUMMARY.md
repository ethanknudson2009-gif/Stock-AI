# Phase D — Multi-Ticker Cross-Sectional Strategy — Plan 01 SUMMARY

**Completed:** 2026-10-13
**Requirements satisfied:** MT-01, MT-02, MT-03, MT-04, MT-05, MT-06

## What shipped

- `stock_ai/strategy/ranker.py` — `top_n(predictions, n)`: per-day equal-weight (1/n) selection of the N highest-probability tickers; NaNs never selected (MT-02).
- `stock_ai/backtest/multi_engine.py`:
  - `canonical_calendar(frames)` — sorted union of all tickers' dates as the reference NYSE trading-day index (MT-03; no external calendar dep — yfinance dates are real sessions).
  - `align_series(..., max_ffill_gap=2)` — reindex each ticker to the calendar, forward-fill only ≤2-session gaps, leave longer gaps NaN (prevents fabricated prices / silent lookahead, Pitfall #5).
  - `run_multi_backtest(returns, weights, cost_bps)` — shifts weights 1 day (no lookahead), builds ONE portfolio daily-return series, Sharpe computed on it (MT-01, MT-04, Pitfall #3). Benchmark = equal-weight-all. Includes turnover cost, max drawdown.
  - `backtest_universe(frames, backend_factory, top_n_count, cost_bps)` — trains one backend per ticker on its own chronological split, takes OOS proba + returns from the held-out slice, aligns, ranks top-N, backtests. Skips tickers that fail to train.
- `app.py` — new "Multi-ticker (cross-sectional)" mode: ticker list or Default Universe, top-N slider, portfolio equity-curve chart, Sharpe labeled "Portfolio Sharpe (equal-weight top-N, daily rebalance)" (MT success criterion 5), survivorship disclosure, skipped-ticker warning. Cached via `@st.cache_data`.

## Tests

`tests/test_multi_engine.py` (7): top-N weighting, NaN never selected, Sharpe≈0 on random signals over 3000 sessions, **portfolio-Sharpe-is-not-average-of-per-ticker-Sharpes** (Pitfall #3 / RH-01 #3 guard — negatively-correlated universe where diversification makes portfolio Sharpe ≫ per-ticker avg), no unexplained NaN days, costs reduce return, calendar-union + align. **28 passed total.**

Verified live: 6-ticker universe OOS (top-3) → 44.0% vs 54.3% equal-weight benchmark, Sharpe 1.06, 0 NaN days. Single-ticker CLI output byte-identical to Phase A checkpoint (MT-05).

## Deviations

- No `pandas_market_calendars` dependency: canonical calendar is derived from the data's own dates per the pitfall's "use SPY/data index as reference" fallback. Simpler and dependency-free; a point-in-time membership feed remains a documented v2 item (MT-06, survivorship bias bounded by short default windows + UI/README disclosure).

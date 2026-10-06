# Codebase Concerns

**Analysis Date:** 2026-09-29 (refreshed 2026-10-06)

## Resolved Since Initial Audit (2026-10-06)

- **In-sample / lookahead-biased backtesting** — fixed in commit `c9fd358`. `train_model` now returns `(model, accuracy, train_df, test_df)` and `cmd_backtest` runs the strategy on the held-out test slice; in-sample numbers are still printed alongside for comparison. Test `tests/test_classifier.py::test_train_test_split_is_chronological_and_disjoint` locks in the no-leakage invariant.
- **No transaction cost modeling** — fixed in commit `790d746`. `run_backtest` accepts `cost_bps` (default 10 bps) and deducts a per-trade cost each time position changes. `n_trades` and `cost_bps` are returned in the result dict. Tests in `tests/test_backtest.py` cover both the "costs reduce return" and "zero-trades = no ongoing cost impact" invariants.
- **No confidence thresholding in signal generation** — fixed in commit `a14d319`. `generate_signals` now uses `predict_proba` and goes long only when `proba_up > threshold` (default 0.5). CLI exposes `--threshold`. Tests in `tests/test_signal.py` cover the threshold invariants.

## Tech Debt (open)

**No caching layer for fetched price data:**
- Issue: `fetch_price_history` (`stock_ai/data/loader.py:7-13`) calls `yfinance` on every invocation with no on-disk or in-memory cache, despite `README.md` describing `stock_ai/data/` as handling "data fetching & caching."
- Files: `stock_ai/data/loader.py`
- Impact: Repeated `fetch`/`train`/`backtest` runs for the same ticker/date range re-download identical data, wasting time and hitting Yahoo Finance rate limits unnecessarily.
- Fix approach: Add a local cache (e.g., parquet/CSV keyed by ticker+date range) with a freshness/TTL check.

**No position sizing / risk management:**
- Issue: `generate_signals` still emits binary long/flat (0/1) positions only — no position sizing (volatility targeting, Kelly), stop-loss, or portfolio-level drawdown halts. Transaction cost modeling and confidence thresholding (both now in place) address some of the original gap, but risk management proper is still absent.
- Files: `stock_ai/strategy/signal.py`, `stock_ai/backtest/engine.py`
- Impact: Backtest and (future) paper trading can place large concentrated positions with no automatic circuit breakers. Flagged as a known v1 gap in `.planning/PROJECT.md`; risk layer is scheduled for v2.
- Fix approach: Add volatility-targeted sizing, a per-trade position cap, and a portfolio-level max drawdown halt. See `.planning/PROJECT.md` risks section.

**No walk-forward backtesting:**
- Issue: Model is trained once on the first 80% of data and evaluated on the next 20%. Doesn't test whether the strategy's edge persists through regime changes.
- Files: `stock_ai/models/classifier.py`, `main.py`
- Impact: A strategy that worked only in 2020-2022 could pass the current single-split backtest. Research-recommended as the highest-information next measurement improvement.
- Fix approach: Rolling retrain window (e.g., 2y train / 6mo test, step forward), aggregate OOS metrics across splits. Scheduled for v2.

## Known Bugs

**RSI division-by-zero produces `inf`/`NaN` silently:**
- Symptoms: `_rsi` in `stock_ai/features/indicators.py:16-21` computes `rs = gain / loss` with no guard when `loss` is 0 (common in strongly trending/illiquid tickers or short windows). This yields `inf`, and `100 - (100/(1+inf))` evaluates to `100.0`, which is arguably correct, but any window where both `gain` and `loss` are exactly 0 produces `0/0 = NaN`, silently dropped later by `.dropna()` in `add_features` (`stock_ai/features/indicators.py:13`).
- Files: `stock_ai/features/indicators.py:16-21`
- Trigger: Tickers/periods with flat price action for the full RSI window (e.g., a halted or extremely low-volume stock).
- Workaround: None currently; rows are silently dropped via `dropna()`, which can shrink the usable dataset without warning.

**`fetch_price_history` return-type ambiguity with yfinance MultiIndex columns:**
- Symptoms: Recent `yfinance` versions can return a `MultiIndex` column DataFrame (ticker level) even for a single ticker in some configurations, which would break downstream column access like `out["Close"]` in `stock_ai/features/indicators.py:9`.
- Files: `stock_ai/data/loader.py:7-13`, `stock_ai/features/indicators.py:9-12`
- Trigger: Depends on installed `yfinance` version behavior (pinned as `yfinance>=0.2` in `requirements.txt:3`, an unbounded upper range).
- Workaround: None; no test currently exercises the real `fetch_price_history` path (see Test Coverage Gaps).

## Security Considerations

**No secrets currently in use, but pattern is unvalidated:**
- Risk: `.env.example` (`.env.example:1-3`) references `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` for a future paid data/broker integration, and `requirements.txt:6` includes `python-dotenv`, but no code currently loads or uses `.env` values (no `load_dotenv()` call found anywhere in `stock_ai/` or `main.py`).
- Files: `.env.example`, `requirements.txt:6`
- Current mitigation: `.env` is presumably gitignored (not verified against `.gitignore` contents beyond existence check), and no live credentials exist yet.
- Recommendations: When broker/API integration is added, ensure `load_dotenv()` is called early in `main.py`, secrets are never logged, and `.env` remains gitignored.

**Unvalidated ticker/date CLI input passed directly to yfinance:**
- Risk: `args.ticker`, `args.start`, `args.end` in `main.py:43-45` are passed unsanitized into `yf.download` (`stock_ai/data/loader.py:9`). Low risk today (no shell/SQL execution), but no input validation exists for malformed dates or tickers beyond yfinance's own error handling.
- Files: `main.py:38-57`, `stock_ai/data/loader.py:7-13`
- Current mitigation: `fetch_price_history` raises `ValueError` if the returned DataFrame is empty (`stock_ai/data/loader.py:10-11`), which catches some invalid-ticker cases.
- Recommendations: Add explicit date format validation and clearer error messages for malformed `--start`/`--end` arguments.

## Performance Bottlenecks

**Full re-fetch + re-train on every CLI invocation:**
- Problem: Every `train` or `backtest` command re-downloads full price history and retrains a 200-tree RandomForest (`n_estimators=200` in `stock_ai/models/classifier.py:27`) from scratch — no model persistence.
- Files: `main.py:18-35`, `stock_ai/models/classifier.py:17-30`
- Cause: No caching of fetched data (see Tech Debt) and no model serialization (e.g., via `joblib`/`pickle`).
- Improvement path: Cache fetched OHLCV data locally; persist trained models to disk keyed by ticker/date range/feature set so repeated `backtest` runs don't retrain unnecessarily.

## Fragile Areas

**Hard-coded feature/label alignment across three modules:**
- Files: `stock_ai/models/classifier.py:7` (`FEATURE_COLUMNS`), `stock_ai/features/indicators.py:6-13` (feature creation), `stock_ai/strategy/signal.py:5,10` (feature consumption)
- Why fragile: `FEATURE_COLUMNS` is a hard-coded list duplicated implicitly by whatever columns `add_features` happens to produce. Adding/renaming a feature in `indicators.py` without also updating `FEATURE_COLUMNS` in `classifier.py` will either silently under-use new features or raise a `KeyError` at training/prediction time with no clear error message tying the two together.
- Safe modification: When adding a new feature column, always update `FEATURE_COLUMNS` in the same change, and add a test asserting the columns produced by `add_features` are a superset of `FEATURE_COLUMNS`.
- Test coverage: No test currently checks this invariant (see Test Coverage Gaps).

**`run_backtest` assumes `df` already contains `return_1d`:**
- Files: `stock_ai/backtest/engine.py:8`, depends on `stock_ai/features/indicators.py:9`
- Why fragile: `run_backtest` directly indexes `df["return_1d"]` with no check that the column exists or that `df` has been through `add_features`. Calling it with a raw price DataFrame raises an unhelpful `KeyError`.
- Safe modification: Add an explicit precondition check/assertion with a clear error message, or accept `returns` as an explicit parameter instead of implicitly coupling to feature-engineering column names.

## Scaling Limits

**Single-ticker, single-process CLI only:**
- Current capacity: `main.py` processes one ticker per invocation with no batching, parallelism, or multi-asset portfolio support.
- Limit: Not designed for scanning/backtesting across a universe of tickers; would require re-running the CLI once per ticker externally.
- Scaling path: Add a batch/portfolio mode that loops over tickers with shared caching and aggregates results, ideally with multiprocessing for the yfinance downloads.

## Dependencies at Risk

**Unbounded/loose version pins:**
- Risk: `requirements.txt` uses only lower-bound pins (`pandas>=2.2`, `numpy>=1.26`, `yfinance>=0.2`, `scikit-learn>=1.5`, `matplotlib>=3.9`, `python-dotenv>=1.0`) with no upper bounds and no lockfile.
- Impact: A fresh `pip install -r requirements.txt` can pull breaking future major versions of any of these libraries (especially `yfinance`, which changes its return schema/behavior frequently between minor versions), causing silent behavior changes or breakage without warning.
- Migration plan: Pin exact versions or add a lockfile (e.g., `pip-tools`/`requirements.lock`) and add CI to catch breakage on dependency updates.

**`yfinance` as sole data source with no fallback:**
- Risk: The entire data pipeline depends on the unofficial `yfinance` package scraping Yahoo Finance, which has no SLA and periodically breaks or gets rate-limited.
- Impact: `fetch_price_history` (`stock_ai/data/loader.py:7-13`) has no retry logic, rate-limit handling, or fallback provider, so any Yahoo-side outage or schema change breaks `fetch`/`train`/`backtest` entirely.
- Migration plan: The `.env.example` hints at an eventual Alpaca integration (`.env.example:2-3`); formalizing a pluggable data-provider interface in `stock_ai/data/` would reduce this single point of failure.

## Missing Critical Features

**No model persistence:**
- Problem: `train_model` returns an in-memory model only; there is no `save`/`load` mechanism (e.g., `joblib.dump`).
- Blocks: Cannot train once and reuse across multiple `backtest` runs, cannot deploy a trained model into a live/paper trading loop as the README's stated goal implies.

**No live/paper trading execution path:**
- Problem: `README.md:3-5` states the goal is "backtests the strategy before any live/paper trading," but no broker integration, order execution, or paper-trading loop exists anywhere in `stock_ai/`.
- Blocks: The project cannot currently act on generated signals beyond printing backtest statistics.

**No configuration file for hyperparameters/thresholds:**
- Problem: RandomForest hyperparameters (`n_estimators=200, max_depth=5, random_state=42` in `stock_ai/models/classifier.py:27`), RSI period (`period=14`), and SMA windows (`10`/`50` in `stock_ai/features/indicators.py:10-11`) are all hard-coded with no config file or CLI overrides.
- Blocks: Experimentation with different feature/model parameters requires code edits rather than config changes.

## Test Coverage Gaps

**Coverage improved on 2026-10-06.** Four test files now exist:
- `tests/test_indicators.py` — feature engineering (original)
- `tests/test_classifier.py` — train/test chronological split + no-leakage invariant
- `tests/test_backtest.py` — transaction cost model (costs reduce returns, zero-trades edge case)
- `tests/test_signal.py` — confidence threshold behavior

**Still untested:**
- `stock_ai/data/loader.py` — `fetch_price_history`'s empty-data `ValueError` path. Needs network mocking (`unittest.mock.patch("stock_ai.data.loader.yf.download")`), none set up yet.
- `main.py` — CLI argument wiring; no end-to-end test exercises `argparse` dispatch.
- Sharpe ratio calculation (`_sharpe_ratio` in `stock_ai/backtest/engine.py:24-27`) — the backtest tests cover `run_backtest` end-to-end but not the zero-std guard directly.
- Priority: Medium — add a `test_loader.py` with a `monkeypatch` for `yf.download` and a direct `_sharpe_ratio` test when adding the next feature.

**No CI configuration:**
- What's not tested: There is no `.github/workflows/`, `tox.ini`, or other CI configuration found in the repo, so `pytest` (available via `.venv/bin/pytest`) is not run automatically on changes.
- Risk: Test suite (currently 1 file) can silently rot or be skipped by contributors.
- Priority: Medium — add a minimal CI workflow running `pytest` on push/PR once the test suite is expanded.

---

*Concerns audit: 2026-09-29*

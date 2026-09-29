<!-- refreshed: 2026-09-29 -->
# Architecture

**Analysis Date:** 2026-09-29

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                      CLI Entry Point                          │
│                     `main.py`                                 │
│      subcommands: fetch | train | backtest                    │
└──────────────────┬──────────────────┬─────────────────────────┘
                    │                  │
                    ▼                  ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│   Data Layer               │  │   Feature Layer                │
│  `stock_ai/data/loader.py` │→│  `stock_ai/features/indicators.py` │
│  fetch_price_history()     │  │  add_features()                │
└──────────────────────────┘  └──────────────┬────────────────┘
                                              │
                                              ▼
                              ┌──────────────────────────────┐
                              │   Model Layer                   │
                              │  `stock_ai/models/classifier.py`│
                              │  build_labels(), train_model()  │
                              └──────────────┬────────────────┘
                                              │
                                              ▼
                              ┌──────────────────────────────┐
                              │   Strategy Layer                │
                              │  `stock_ai/strategy/signal.py`  │
                              │  generate_signals()             │
                              └──────────────┬────────────────┘
                                              │
                                              ▼
                              ┌──────────────────────────────┐
                              │   Backtest Layer                │
                              │  `stock_ai/backtest/engine.py`  │
                              │  run_backtest()                 │
                              └──────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| CLI entry point | Parse args, wire commands to the pipeline, print results | `main.py` |
| Data loader | Fetch daily OHLCV history from Yahoo Finance via `yfinance` | `stock_ai/data/loader.py` |
| Feature engineering | Compute derived indicator columns (returns, SMAs, RSI) from OHLCV | `stock_ai/features/indicators.py` |
| Model training | Build up/down labels, split train/test, fit a `RandomForestClassifier` | `stock_ai/models/classifier.py` |
| Signal generation | Convert model predictions into long/flat position series | `stock_ai/strategy/signal.py` |
| Backtest engine | Apply positions to returns (with lag), compute return/Sharpe metrics | `stock_ai/backtest/engine.py` |

## Pattern Overview

**Overall:** Linear data pipeline / functional module composition. Each stage is a pure(ish) function that takes a pandas `DataFrame`/`Series` and returns a transformed one; there is no class-based service layer, no dependency injection, and no persistence layer beyond in-memory pandas objects.

**Key Characteristics:**
- Stateless functions per stage — one function per pipeline step, no shared mutable objects.
- Data flows as a single `pandas.DataFrame` threaded through each stage (loader → features → model → strategy → backtest).
- No web server, no database, no background jobs — this is a CLI/batch script architecture.
- Package (`stock_ai`) organized by pipeline stage (data, features, models, strategy, backtest), mirrored 1:1 by directory name.

## Layers

**CLI Layer:**
- Purpose: parse command-line args and orchestrate calls into the `stock_ai` package
- Location: `main.py`
- Contains: `argparse` setup, `cmd_fetch`/`cmd_train`/`cmd_backtest` handlers
- Depends on: all `stock_ai.*` modules
- Used by: end user via `python main.py <command>`

**Data Layer:**
- Purpose: retrieve raw market data
- Location: `stock_ai/data/loader.py`
- Contains: `fetch_price_history()` — thin wrapper around `yfinance.download`
- Depends on: `yfinance`, `pandas`
- Used by: `main.py`

**Feature Layer:**
- Purpose: transform raw OHLCV into model-ready indicator columns
- Location: `stock_ai/features/indicators.py`
- Contains: `add_features()`, private `_rsi()` helper
- Depends on: `pandas`
- Used by: `main.py`, `tests/test_indicators.py`

**Model Layer:**
- Purpose: label data and train a classifier to predict next-day direction
- Location: `stock_ai/models/classifier.py`
- Contains: `FEATURE_COLUMNS` constant, `build_labels()`, `train_model()`
- Depends on: `pandas`, `scikit-learn` (`RandomForestClassifier`, `train_test_split`)
- Used by: `main.py`, `stock_ai/strategy/signal.py` (imports `FEATURE_COLUMNS`)

**Strategy Layer:**
- Purpose: convert model predictions into trade positions
- Location: `stock_ai/strategy/signal.py`
- Contains: `generate_signals()`
- Depends on: `stock_ai.models.classifier.FEATURE_COLUMNS`
- Used by: `main.py`

**Backtest Layer:**
- Purpose: simulate strategy performance against buy-and-hold
- Location: `stock_ai/backtest/engine.py`
- Contains: `run_backtest()`, private `_sharpe_ratio()`
- Depends on: `pandas`
- Used by: `main.py`

## Data Flow

### Primary Request Path (`python main.py backtest --ticker AAPL`)

1. `main.py` parses args and calls `cmd_backtest()` (`main.py:25`)
2. `fetch_price_history(ticker, start, end)` downloads OHLCV via yfinance (`stock_ai/data/loader.py:7`)
3. `add_features(df)` appends `return_1d`, `sma_10`, `sma_50`, `rsi_14`, drops NaN rows (`stock_ai/features/indicators.py:6`)
4. `train_model(df)` labels rows via `build_labels()`, splits train/test (80/20, no shuffle), fits `RandomForestClassifier` (`stock_ai/models/classifier.py:17`)
5. `generate_signals(model, df)` runs `model.predict()` over the **full** `df` (not just the held-out test split) to produce a position series (`stock_ai/strategy/signal.py:8`)
6. `run_backtest(df, positions)` shifts positions by 1 day (avoids same-day lookahead), multiplies by `return_1d`, computes cumulative return, buy-hold return, and Sharpe ratio (`stock_ai/backtest/engine.py:6`)
7. `main.py` prints accuracy, strategy return, buy-hold return, Sharpe ratio (`main.py:32-35`)

**State Management:**
- No persisted state. Each CLI invocation re-fetches data and retrains the model from scratch; nothing is cached or written to disk.

## Key Abstractions

**Pipeline Stage Function:**
- Purpose: each stage is a single top-level function accepting and returning pandas objects
- Examples: `fetch_price_history()` (`stock_ai/data/loader.py`), `add_features()` (`stock_ai/features/indicators.py`), `train_model()` (`stock_ai/models/classifier.py`), `generate_signals()` (`stock_ai/strategy/signal.py`), `run_backtest()` (`stock_ai/backtest/engine.py`)
- Pattern: input `DataFrame`/`Series` → transform → output `DataFrame`/`Series`/`tuple`/`dict`; no side effects, no classes

**Shared Constant Contract:**
- Purpose: `FEATURE_COLUMNS` in `stock_ai/models/classifier.py:7` is the single source of truth for which columns the model consumes, imported by `stock_ai/strategy/signal.py:5` to keep training and inference features aligned

## Entry Points

**CLI (`main.py`):**
- Location: `main.py`
- Triggers: `python main.py {fetch,train,backtest} --ticker TICKER [--start DATE] [--end DATE]`
- Responsibilities: argument parsing, dispatching to `cmd_fetch`/`cmd_train`/`cmd_backtest`, printing results to stdout

**Tests (`tests/`):**
- Location: `tests/test_indicators.py`
- Triggers: test runner (pytest, inferred from style; no config file present)
- Responsibilities: verify `add_features()` produces expected columns

## Architectural Constraints

- **Threading:** Single-threaded, synchronous script execution. No async/await, no worker threads.
- **Global state:** None observed — no module-level singletons or shared mutable state.
- **Circular imports:** None. Import direction is strictly one-way: `strategy` → `models`; `main.py` → all stage modules. No back-references.
- **In-sample bias:** `generate_signals()` predicts over the entire dataset (including rows used for training in `train_model()`), so `backtest`'s reported returns are optimistic/in-sample rather than true out-of-sample results. Documented as a known limitation in `README.md`.
- **No persistence:** Data, models, and results are never written to disk or a database; every run is fully ephemeral and recomputed from the API.

## Anti-Patterns

### Look-Ahead Bias in Backtest Signal Generation

**What happens:** `cmd_backtest()` in `main.py:25-30` calls `train_model(df)` (which internally splits `df` 80/20 and fits on the first 80%) and then calls `generate_signals(model, df)` passing the **same full `df`**, so the model predicts on rows it was trained on.
**Why it's wrong:** The reported `Strategy return` and `Sharpe ratio` reflect performance partly on data the model has already seen, inflating apparent skill.
**Do this instead:** Generate signals only on the held-out test split (or refactor `train_model` to also return the train/test index boundary) before backtesting, per the fix noted in `README.md`.

## Error Handling

**Strategy:** Minimal, fail-fast. Only one explicit validation exists.

**Patterns:**
- `fetch_price_history()` raises `ValueError` if `yfinance` returns an empty `DataFrame` (`stock_ai/data/loader.py:10-11`).
- No try/except blocks anywhere else in the pipeline — network errors, NaN propagation, and sklearn exceptions propagate uncaught to the CLI, which will crash with a raw traceback.

## Cross-Cutting Concerns

**Logging:** None. Output is via `print()` statements in `main.py` only.
**Validation:** Only ticker/date validity is implicitly checked via the yfinance empty-result guard; no schema/type validation elsewhere.
**Authentication:** Not applicable for current data source (`yfinance` public endpoint); `.env.example` exists for future paid data/broker provider API keys but nothing currently reads env vars in code.

---

*Architecture analysis: 2026-09-29*

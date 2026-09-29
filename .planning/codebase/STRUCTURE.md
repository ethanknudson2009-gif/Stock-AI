# Codebase Structure

**Analysis Date:** 2026-09-29

## Directory Layout

```
Stock-AI/
├── main.py              # CLI entry point (fetch / train / backtest subcommands)
├── requirements.txt     # Python dependencies (pandas, numpy, yfinance, scikit-learn, matplotlib, python-dotenv)
├── README.md             # Project overview, layout, setup, usage, known limitations
├── .env.example          # Template for optional broker/data-provider API keys (currently unused by code)
├── .gitignore            # Ignores .venv, __pycache__, .env, data/model artifacts, OS/editor files
├── stock_ai/              # Main Python package, organized by pipeline stage
│   ├── __init__.py
│   ├── data/              # Data fetching & caching (price history, fundamentals)
│   │   ├── __init__.py
│   │   └── loader.py       # fetch_price_history() — yfinance OHLCV download
│   ├── features/           # Feature engineering (indicators, labels)
│   │   ├── __init__.py
│   │   └── indicators.py   # add_features(), _rsi() — SMA/RSI/return columns
│   ├── models/             # Model training/inference
│   │   ├── __init__.py
│   │   └── classifier.py   # FEATURE_COLUMNS, build_labels(), train_model()
│   ├── strategy/            # Signal -> position sizing / trade decisions
│   │   ├── __init__.py
│   │   └── signal.py        # generate_signals()
│   └── backtest/             # Backtesting engine + performance metrics
│       ├── __init__.py
│       └── engine.py          # run_backtest(), _sharpe_ratio()
├── tests/                  # Unit tests (mirrors stock_ai/ package structure)
│   ├── __init__.py
│   └── test_indicators.py   # Tests for stock_ai/features/indicators.py
└── .venv/                   # Local virtualenv (gitignored, not committed)
```

## Directory Purposes

**`stock_ai/data/`:**
- Purpose: retrieving raw market data from external sources
- Contains: one module (`loader.py`) wrapping `yfinance.download`
- Key files: `stock_ai/data/loader.py`

**`stock_ai/features/`:**
- Purpose: transforming raw OHLCV data into model-ready indicator columns
- Contains: `indicators.py` with public `add_features()` and private `_rsi()` helper
- Key files: `stock_ai/features/indicators.py`

**`stock_ai/models/`:**
- Purpose: labeling data and training the price-direction classifier
- Contains: `classifier.py` with the shared `FEATURE_COLUMNS` constant, labeling, and training logic
- Key files: `stock_ai/models/classifier.py`

**`stock_ai/strategy/`:**
- Purpose: turning model predictions into long/flat trading positions
- Contains: `signal.py`
- Key files: `stock_ai/strategy/signal.py`

**`stock_ai/backtest/`:**
- Purpose: simulating strategy performance against buy-and-hold and computing metrics (return, Sharpe)
- Contains: `engine.py`
- Key files: `stock_ai/backtest/engine.py`

**`tests/`:**
- Purpose: unit tests for `stock_ai` modules
- Contains: one test file so far (`test_indicators.py`), covering only `features/indicators.py`
- Key files: `tests/test_indicators.py`

## Key File Locations

**Entry Points:**
- `main.py`: CLI argument parsing and command dispatch (`fetch`, `train`, `backtest`)

**Configuration:**
- `.env.example`: template for optional API keys (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`); no `.env` reading code exists yet despite `python-dotenv` being a dependency
- `requirements.txt`: pinned minimum versions for all dependencies

**Core Logic:**
- `stock_ai/data/loader.py`: data acquisition
- `stock_ai/features/indicators.py`: feature engineering
- `stock_ai/models/classifier.py`: labeling + model training
- `stock_ai/strategy/signal.py`: signal generation
- `stock_ai/backtest/engine.py`: backtest simulation and metrics

**Testing:**
- `tests/test_indicators.py`: only existing test module

## Naming Conventions

**Files:**
- Lowercase snake_case module names matching their primary responsibility (e.g., `loader.py`, `indicators.py`, `classifier.py`, `signal.py`, `engine.py`)
- Test files prefixed `test_` and named after the module under test (e.g., `test_indicators.py` tests `indicators.py`)

**Directories:**
- Lowercase, singular-vs-plural varies by domain noun: `data/`, `features/`, `models/`, `strategy/` (singular), `backtest/` (singular) — directory name equals the pipeline stage name
- Each package directory contains an `__init__.py` (currently empty in all cases) marking it as a Python package

**Functions:**
- Public functions: verb-first snake_case describing the transform, e.g. `fetch_price_history()`, `add_features()`, `build_labels()`, `train_model()`, `generate_signals()`, `run_backtest()`
- Private/internal helpers: leading underscore, e.g. `_rsi()`, `_sharpe_ratio()`

**Constants:**
- Upper snake_case module-level constants, e.g. `FEATURE_COLUMNS` in `stock_ai/models/classifier.py:7`

## Where to Add New Code

**New Feature (e.g., new indicator):**
- Primary code: add function to `stock_ai/features/indicators.py`, or create a new module in `stock_ai/features/` if the indicator family is large; wire into `add_features()`
- Update `FEATURE_COLUMNS` in `stock_ai/models/classifier.py` if the new column should feed the model
- Tests: `tests/test_indicators.py` (or a new `tests/test_<feature>.py` file mirroring the module name)

**New Data Source:**
- Implementation: new module under `stock_ai/data/` (e.g., `stock_ai/data/fundamentals.py`), following the pattern of `loader.py` (single function returning a `pandas.DataFrame`, raising `ValueError` on empty/invalid results)

**New Model/Strategy Variant:**
- Model changes: `stock_ai/models/classifier.py` (or new module in `stock_ai/models/` for alternative model types)
- Strategy changes: `stock_ai/strategy/signal.py` (or new module in `stock_ai/strategy/` for alternative position-sizing logic)

**New CLI Command:**
- Add a `cmd_<name>()` function and `sub.add_parser(...)` block in `main.py`, following the existing `cmd_fetch`/`cmd_train`/`cmd_backtest` pattern

**Utilities:**
- No shared `utils/` module exists yet. If cross-cutting helpers are needed (e.g., date parsing, config loading), create `stock_ai/utils.py` or a `stock_ai/config.py` for `.env`/dotenv loading (currently unused despite the dependency being present).

## Special Directories

**`.venv/`:**
- Purpose: local Python virtual environment created via `python3 -m venv .venv` per `README.md`
- Generated: Yes
- Committed: No (excluded via `.gitignore`)

**`data/raw/`, `data/cache/`, `models/*.pkl` (referenced in `.gitignore` but not yet present):**
- Purpose: reserved locations for cached data and serialized model artifacts, anticipated but not yet implemented in code (no caching or model persistence logic exists in `stock_ai/` currently)
- Generated: Would be, once implemented
- Committed: No (pre-emptively excluded via `.gitignore`)

---

*Structure analysis: 2026-09-29*

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Stock-AI — Project**

A learning-by-building project aimed at a specific target: a **Jev-powered automated stock trading bot that paper-trades a broad universe of US equities on a daily cadence**, backed by a browser-based backtest explorer so decisions can be inspected before any paper order gets placed.

It starts from the existing Stock-AI Python codebase (yfinance → scikit-learn RandomForest → long/flat backtest) and grows it into a running bot connected to Alpaca's paper-trading sandbox, with Jev as the signal classifier replacing or augmenting the current RandomForest.

The underlying motivation is **learning algorithmic trading, AI integration, and real-world system plumbing by shipping something that actually runs** — not building an edge that beats the market. Any alpha discovered is a bonus; the primary deliverable is a working bot and the understanding that comes from shipping it.

**Core Value:** **One thing that must work:** a running Alpaca paper-trading bot that places real sandbox orders based on daily EOD signals, backed by an honest backtest explorer the owner (and friends/mentors) can open in a browser.

Everything else — fancier features, risk layers, LLM-powered news reading — is secondary to this core loop running end-to-end.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 (3.12.7 per `.venv/pyvenv.cfg`) - Entire codebase (`main.py`, `stock_ai/`, `tests/`)
- None detected
## Runtime
- CPython 3.12.7
- Virtual environment at `.venv/` (created via `python3 -m venv .venv`), excluded from git via `.gitignore`
- pip
- Lockfile: missing (no `requirements.lock`, `Pipfile.lock`, or `poetry.lock` present) — `requirements.txt` uses loose `>=` version constraints only
## Frameworks
- None (no web framework) — this is a CLI/data-science toolkit, not a service
- `argparse` (stdlib) - CLI argument parsing and subcommand dispatch, see `main.py`
- pytest (implied by `tests/` layout and `test_*.py` naming in `tests/test_indicators.py`) - not pinned in `requirements.txt`; ensure it's installed separately or added as a dev dependency
- None detected (no bundler, no `Makefile`, no `pyproject.toml`, no `setup.py`)
## Key Dependencies
- `pandas>=2.2` - Core dataframe representation for price history, features, and backtest results throughout `stock_ai/`
- `numpy>=1.26` - Numerical operations backing pandas
- `yfinance>=0.2` - Sole market data source; wraps Yahoo Finance in `stock_ai/data/loader.py`
- `scikit-learn>=1.5` - `RandomForestClassifier` and `train_test_split` used in `stock_ai/models/classifier.py`
- `python-dotenv>=1.0` - Loads `.env` for optional API keys (declared as a dependency but not yet imported/used anywhere in `stock_ai/` — dead dependency today)
- `matplotlib>=3.9` - Declared for plotting but not currently imported anywhere in `stock_ai/` or `main.py` (unused today, likely intended for future backtest visualization)
## Configuration
- `.env.example` documents two optional variables: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` (both commented out, "only needed if you swap yfinance for a paid data/broker API")
- `.env` is gitignored and not present in the repo; no code currently reads these variables (no `os.environ`/`dotenv.load_dotenv()` calls found in `stock_ai/` or `main.py`)
- No build config files present. Project runs directly via `python main.py <command>`.
## Platform Requirements
- Python 3.12+ toolchain
- `pip install -r requirements.txt` inside a virtualenv (see `README.md` Setup section)
- No deployment target defined — this is a local CLI script, not a deployed service. No Docker, CI, or hosting config present.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Lowercase, `snake_case`, one module per concern: `loader.py`, `indicators.py`, `classifier.py`, `signal.py`, `engine.py`
- Module name matches its primary responsibility (e.g. `stock_ai/backtest/engine.py` holds `run_backtest`)
- `snake_case`, verb-first for actions: `fetch_price_history`, `add_features`, `train_model`, `generate_signals`, `run_backtest`
- Private/internal helpers prefixed with a single underscore: `_rsi` (`stock_ai/features/indicators.py:16`), `_sharpe_ratio` (`stock_ai/backtest/engine.py:24`)
- CLI command handlers follow `cmd_<verb>` pattern: `cmd_fetch`, `cmd_train`, `cmd_backtest` (`main.py:13,18,25`)
- `snake_case` throughout: `strategy_returns`, `buy_hold_return`, `test_accuracy`
- DataFrame convention: input DataFrame is `df`; a locally modified copy is `out` (see `stock_ai/features/indicators.py:8`, `stock_ai/models/classifier.py:12`)
- ML convention: `X`/`X_train`/`X_test` (feature matrix, capitalized per scikit-learn convention) and `y`/`y_train`/`y_test` (labels) — see `stock_ai/models/classifier.py:20-25`
- No custom classes yet; only functions and module-level constants
- Module-level constants are `UPPER_SNAKE_CASE`: `FEATURE_COLUMNS = ["return_1d", "sma_10", "sma_50", "rsi_14"]` (`stock_ai/models/classifier.py:7`)
## Code Style
- No formatter config present (no `black`, `ruff format`, or `pyproject.toml`) — code is hand-formatted but consistently PEP 8-ish (4-space indent, ~88-100 col lines)
- When adding a formatter, `black` with default line length is the natural fit given existing line lengths
- No linter config present (no `.flake8`, `ruff.toml`, `pyproject.toml`, or `setup.cfg`)
- No enforced style rules beyond convention consistency observed in existing files
- Full type hints on public function signatures, including modern `X | None` union syntax (Python 3.10+): `def fetch_price_history(ticker: str, start: str, end: str | None = None) -> pd.DataFrame:` (`stock_ai/data/loader.py:7`)
- Return type of `tuple[RandomForestClassifier, float]` used directly rather than `Tuple` from `typing` (`stock_ai/models/classifier.py:17`)
- No `mypy` or other type-checker config present — hints are documentation-only, not enforced
## Import Organization
- None. All internal imports are absolute, fully-qualified (`stock_ai.data.loader`, `stock_ai.features.indicators`, etc.) — no relative imports (`from . import`) observed.
## Error Handling
- Fail fast with a descriptive `ValueError` at the boundary where bad input is detected, rather than silently returning empty/default data: `if df.empty: raise ValueError(f"No price data returned for ticker '{ticker}'")` (`stock_ai/data/loader.py:10-11`)
- No `try/except` blocks anywhere in `stock_ai/` — errors from library calls (e.g. `yfinance`, `sklearn`) are allowed to propagate uncaught
- No custom exception classes; standard library exceptions (`ValueError`) are used directly
- When adding new modules, prefer raising a specific built-in exception with an f-string message naming the offending value, matching the one existing example
## Logging
- CLI output uses plain `print()` for user-facing results (`main.py:15,22,32-35`)
- No structured logging, no log levels, no log files
- If logging is introduced, it should be scoped to `main.py`/CLI layer first since library modules (`stock_ai/*`) currently have zero I/O side effects beyond `fetch_price_history`'s network call
## Comments
- Every module has a one-line module-level docstring describing its purpose, e.g. `"""Simple long/flat backtester: apply positions to returns and report performance."""` (`stock_ai/backtest/engine.py:1`)
- Every public function has a one-line docstring stating what it does, often naming key parameters with backticks: `"""Download daily OHLCV history for `ticker` between `start` and `end`."""` (`stock_ai/data/loader.py:8`)
- Inline comments are rare and used only to flag non-obvious correctness concerns, e.g. noting lookahead-bias avoidance: `"""Apply `positions` (shifted by 1 day to avoid lookahead) to daily returns."""` (`stock_ai/backtest/engine.py:7`)
- No comments explaining "what" the code does line-by-line — comments/docstrings explain intent/purpose only
- Not applicable (Python project). Docstrings use plain triple-quoted `"""..."""` single-line style, not Google/NumPy/Sphinx multi-section format. Keep new docstrings to this same single-line, backtick-quoted-parameter style unless a function's behavior needs multi-line explanation.
## Function Design
- Single DataFrame/Series for transformation functions (`add_features`, `generate_signals`)
- Tuple of `(model, metric)` when a function produces both an artifact and a scalar result: `train_model` returns `(model, accuracy)` (`stock_ai/models/classifier.py:17`)
- Plain `dict` with named keys for multi-metric results: `run_backtest` returns `{"total_return", "buy_hold_return", "sharpe_ratio", "cumulative_returns"}` (`stock_ai/backtest/engine.py:16-21`) — prefer this dict-of-named-metrics pattern over inventing a results class
## Module Design
## Package Structure Convention
- `stock_ai/data/` — fetching/loading raw price data
- `stock_ai/features/` — feature engineering on top of raw data
- `stock_ai/models/` — model training/labeling
- `stock_ai/strategy/` — turning model output into trade signals
- `stock_ai/backtest/` — evaluating strategy performance
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
```
## Component Responsibilities
| Component | Responsibility | File |
|-----------|----------------|------|
| CLI entry point | Parse args, wire commands to the pipeline, print results | `main.py` |
| Data loader | Fetch daily OHLCV history from Yahoo Finance via `yfinance` | `stock_ai/data/loader.py` |
| Feature engineering | Compute derived indicator columns (returns, SMAs, RSI) from OHLCV | `stock_ai/features/indicators.py` |
| Model training | Build up/down labels, split train/test chronologically, fit a `RandomForestClassifier`, return model + accuracy + train/test slices | `stock_ai/models/classifier.py` |
| Signal generation | Convert model probabilities into long/flat positions via a configurable confidence threshold | `stock_ai/strategy/signal.py` |
| Backtest engine | Apply positions to returns (with lag), deduct per-trade transaction costs, compute return/Sharpe/trade-count metrics | `stock_ai/backtest/engine.py` |
## Pattern Overview
- Stateless functions per stage — one function per pipeline step, no shared mutable objects.
- Data flows as a single `pandas.DataFrame` threaded through each stage (loader → features → model → strategy → backtest).
- No web server, no database, no background jobs — this is a CLI/batch script architecture.
- Package (`stock_ai`) organized by pipeline stage (data, features, models, strategy, backtest), mirrored 1:1 by directory name.
## Layers
- Purpose: parse command-line args and orchestrate calls into the `stock_ai` package
- Location: `main.py`
- Contains: `argparse` setup, `cmd_fetch`/`cmd_train`/`cmd_backtest` handlers
- Depends on: all `stock_ai.*` modules
- Used by: end user via `python main.py <command>`
- Purpose: retrieve raw market data
- Location: `stock_ai/data/loader.py`
- Contains: `fetch_price_history()` — thin wrapper around `yfinance.download`
- Depends on: `yfinance`, `pandas`
- Used by: `main.py`
- Purpose: transform raw OHLCV into model-ready indicator columns
- Location: `stock_ai/features/indicators.py`
- Contains: `add_features()`, private `_rsi()` helper
- Depends on: `pandas`
- Used by: `main.py`, `tests/test_indicators.py`
- Purpose: label data and train a classifier to predict next-day direction
- Location: `stock_ai/models/classifier.py`
- Contains: `FEATURE_COLUMNS` constant, `build_labels()`, `train_model()`
- Depends on: `pandas`, `scikit-learn` (`RandomForestClassifier`, `train_test_split`)
- Used by: `main.py`, `stock_ai/strategy/signal.py` (imports `FEATURE_COLUMNS`)
- Purpose: convert model predictions into trade positions
- Location: `stock_ai/strategy/signal.py`
- Contains: `generate_signals()`
- Depends on: `stock_ai.models.classifier.FEATURE_COLUMNS`
- Used by: `main.py`
- Purpose: simulate strategy performance against buy-and-hold
- Location: `stock_ai/backtest/engine.py`
- Contains: `run_backtest()`, private `_sharpe_ratio()`
- Depends on: `pandas`
- Used by: `main.py`
## Data Flow
### Primary Request Path (`python main.py backtest --ticker AAPL`)
- No persisted state. Each CLI invocation re-fetches data and retrains the model from scratch; nothing is cached or written to disk.
## Key Abstractions
- Purpose: each stage is a single top-level function accepting and returning pandas objects
- Examples: `fetch_price_history()` (`stock_ai/data/loader.py`), `add_features()` (`stock_ai/features/indicators.py`), `train_model()` (`stock_ai/models/classifier.py`), `generate_signals()` (`stock_ai/strategy/signal.py`), `run_backtest()` (`stock_ai/backtest/engine.py`)
- Pattern: input `DataFrame`/`Series` → transform → output `DataFrame`/`Series`/`tuple`/`dict`; no side effects, no classes
- Purpose: `FEATURE_COLUMNS` in `stock_ai/models/classifier.py:7` is the single source of truth for which columns the model consumes, imported by `stock_ai/strategy/signal.py:5` to keep training and inference features aligned
## Entry Points
- Location: `main.py`
- Triggers: `python main.py {fetch,train,backtest} --ticker TICKER [--start DATE] [--end DATE]`
- Responsibilities: argument parsing, dispatching to `cmd_fetch`/`cmd_train`/`cmd_backtest`, printing results to stdout
- Location: `tests/test_indicators.py`
- Triggers: test runner (pytest, inferred from style; no config file present)
- Responsibilities: verify `add_features()` produces expected columns
## Architectural Constraints
- **Threading:** Single-threaded, synchronous script execution. No async/await, no worker threads.
- **Global state:** None observed — no module-level singletons or shared mutable state.
- **Circular imports:** None. Import direction is strictly one-way: `strategy` → `models`; `main.py` → all stage modules. No back-references.
- **Honest out-of-sample reporting** (as of 2026-10-06): `generate_signals()` runs on the held-out `test_df` returned from `train_model()`, so backtest OOS numbers are not polluted by training rows. In-sample numbers are also printed for comparison so the overfitting gap is explicit.
- **No persistence:** Data, models, and results are never written to disk or a database; every run is fully ephemeral and recomputed from the API.
## Error Handling
- `fetch_price_history()` raises `ValueError` if `yfinance` returns an empty `DataFrame` (`stock_ai/data/loader.py:10-11`).
- No try/except blocks anywhere else in the pipeline — network errors, NaN propagation, and sklearn exceptions propagate uncaught to the CLI, which will crash with a raw traceback.
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

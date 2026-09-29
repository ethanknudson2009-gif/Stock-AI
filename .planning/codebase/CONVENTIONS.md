# Coding Conventions

**Analysis Date:** 2026-09-29

## Naming Patterns

**Files:**
- Lowercase, `snake_case`, one module per concern: `loader.py`, `indicators.py`, `classifier.py`, `signal.py`, `engine.py`
- Module name matches its primary responsibility (e.g. `stock_ai/backtest/engine.py` holds `run_backtest`)

**Functions:**
- `snake_case`, verb-first for actions: `fetch_price_history`, `add_features`, `train_model`, `generate_signals`, `run_backtest`
- Private/internal helpers prefixed with a single underscore: `_rsi` (`stock_ai/features/indicators.py:16`), `_sharpe_ratio` (`stock_ai/backtest/engine.py:24`)
- CLI command handlers follow `cmd_<verb>` pattern: `cmd_fetch`, `cmd_train`, `cmd_backtest` (`main.py:13,18,25`)

**Variables:**
- `snake_case` throughout: `strategy_returns`, `buy_hold_return`, `test_accuracy`
- DataFrame convention: input DataFrame is `df`; a locally modified copy is `out` (see `stock_ai/features/indicators.py:8`, `stock_ai/models/classifier.py:12`)
- ML convention: `X`/`X_train`/`X_test` (feature matrix, capitalized per scikit-learn convention) and `y`/`y_train`/`y_test` (labels) — see `stock_ai/models/classifier.py:20-25`

**Types:**
- No custom classes yet; only functions and module-level constants
- Module-level constants are `UPPER_SNAKE_CASE`: `FEATURE_COLUMNS = ["return_1d", "sma_10", "sma_50", "rsi_14"]` (`stock_ai/models/classifier.py:7`)

## Code Style

**Formatting:**
- No formatter config present (no `black`, `ruff format`, or `pyproject.toml`) — code is hand-formatted but consistently PEP 8-ish (4-space indent, ~88-100 col lines)
- When adding a formatter, `black` with default line length is the natural fit given existing line lengths

**Linting:**
- No linter config present (no `.flake8`, `ruff.toml`, `pyproject.toml`, or `setup.cfg`)
- No enforced style rules beyond convention consistency observed in existing files

**Type hints:**
- Full type hints on public function signatures, including modern `X | None` union syntax (Python 3.10+): `def fetch_price_history(ticker: str, start: str, end: str | None = None) -> pd.DataFrame:` (`stock_ai/data/loader.py:7`)
- Return type of `tuple[RandomForestClassifier, float]` used directly rather than `Tuple` from `typing` (`stock_ai/models/classifier.py:17`)
- No `mypy` or other type-checker config present — hints are documentation-only, not enforced

## Import Organization

**Order:**
1. Standard library imports (`argparse`, `from datetime import date`)
2. Third-party imports (`pandas`, `yfinance`, `sklearn.*`)
3. Local package imports, using absolute imports rooted at `stock_ai` (`from stock_ai.models.classifier import FEATURE_COLUMNS`)

Blank line separates each group; see `main.py:3-10` for the clearest example (stdlib, blank line, then five `stock_ai.*` imports in alphabetical module order).

**Path Aliases:**
- None. All internal imports are absolute, fully-qualified (`stock_ai.data.loader`, `stock_ai.features.indicators`, etc.) — no relative imports (`from . import`) observed.

## Error Handling

**Patterns:**
- Fail fast with a descriptive `ValueError` at the boundary where bad input is detected, rather than silently returning empty/default data: `if df.empty: raise ValueError(f"No price data returned for ticker '{ticker}'")` (`stock_ai/data/loader.py:10-11`)
- No `try/except` blocks anywhere in `stock_ai/` — errors from library calls (e.g. `yfinance`, `sklearn`) are allowed to propagate uncaught
- No custom exception classes; standard library exceptions (`ValueError`) are used directly
- When adding new modules, prefer raising a specific built-in exception with an f-string message naming the offending value, matching the one existing example

## Logging

**Framework:** None — no `logging` module usage anywhere in the codebase

**Patterns:**
- CLI output uses plain `print()` for user-facing results (`main.py:15,22,32-35`)
- No structured logging, no log levels, no log files
- If logging is introduced, it should be scoped to `main.py`/CLI layer first since library modules (`stock_ai/*`) currently have zero I/O side effects beyond `fetch_price_history`'s network call

## Comments

**When to Comment:**
- Every module has a one-line module-level docstring describing its purpose, e.g. `"""Simple long/flat backtester: apply positions to returns and report performance."""` (`stock_ai/backtest/engine.py:1`)
- Every public function has a one-line docstring stating what it does, often naming key parameters with backticks: `"""Download daily OHLCV history for `ticker` between `start` and `end`."""` (`stock_ai/data/loader.py:8`)
- Inline comments are rare and used only to flag non-obvious correctness concerns, e.g. noting lookahead-bias avoidance: `"""Apply `positions` (shifted by 1 day to avoid lookahead) to daily returns."""` (`stock_ai/backtest/engine.py:7`)
- No comments explaining "what" the code does line-by-line — comments/docstrings explain intent/purpose only

**JSDoc/TSDoc:**
- Not applicable (Python project). Docstrings use plain triple-quoted `"""..."""` single-line style, not Google/NumPy/Sphinx multi-section format. Keep new docstrings to this same single-line, backtick-quoted-parameter style unless a function's behavior needs multi-line explanation.

## Function Design

**Size:** Small and single-purpose — every function in `stock_ai/` is under 15 lines. Each module exposes one primary public function plus at most one private helper (e.g. `add_features` + `_rsi`, `run_backtest` + `_sharpe_ratio`).

**Parameters:** Plain positional/keyword parameters with defaults for optional behavior (`end: str | None = None`, `period: int = 14`). No `**kwargs`/config-object pattern used.

**Return Values:**
- Single DataFrame/Series for transformation functions (`add_features`, `generate_signals`)
- Tuple of `(model, metric)` when a function produces both an artifact and a scalar result: `train_model` returns `(model, accuracy)` (`stock_ai/models/classifier.py:17`)
- Plain `dict` with named keys for multi-metric results: `run_backtest` returns `{"total_return", "buy_hold_return", "sharpe_ratio", "cumulative_returns"}` (`stock_ai/backtest/engine.py:16-21`) — prefer this dict-of-named-metrics pattern over inventing a results class

## Module Design

**Exports:** No `__all__` declarations; every `stock_ai/**/__init__.py` file is empty. Modules are imported by their fully-qualified submodule path (`from stock_ai.backtest.engine import run_backtest`), not re-exported through package `__init__.py`.

**Barrel Files:** Not used. Each `__init__.py` in `stock_ai/`, `stock_ai/data/`, `stock_ai/features/`, `stock_ai/models/`, `stock_ai/strategy/`, `stock_ai/backtest/` is empty — package `__init__.py` files exist only to mark packages, not to aggregate exports. Follow this pattern for new submodules: add the file under its own subpackage and import it by full path from call sites.

## Package Structure Convention

The codebase follows a single-responsibility pipeline layout, one subpackage per pipeline stage:
- `stock_ai/data/` — fetching/loading raw price data
- `stock_ai/features/` — feature engineering on top of raw data
- `stock_ai/models/` — model training/labeling
- `stock_ai/strategy/` — turning model output into trade signals
- `stock_ai/backtest/` — evaluating strategy performance

New pipeline stages should follow this same pattern: one subpackage, one primary public function named after the action it performs, plumbed together only from `main.py`.

---

*Convention analysis: 2026-09-29*

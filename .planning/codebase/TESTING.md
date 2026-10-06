# Testing Patterns

**Analysis Date:** 2026-09-29 (refreshed 2026-10-06 — three new test files added)

## Test Framework

**Runner:**
- `pytest` (installed in `.venv`, binary present at `.venv/bin/pytest`) — not declared in `requirements.txt`, so it must be installed separately (e.g. `pip install pytest`) before running tests
- Config: None — no `pytest.ini`, `pyproject.toml`, or `setup.cfg` present anywhere in the repo. Pytest runs with default discovery settings.

**Assertion Library:**
- Plain built-in `assert` statements (pytest's assertion rewriting), no `unittest.TestCase`, no `assertpy`/`hamcrest`/etc.

**Run Commands:**
```bash
pytest                  # Run all tests (auto-discovers tests/ directory)
pytest -v                # Verbose output
pytest tests/test_indicators.py   # Run a single test file
```
No watch mode or coverage command is configured (no `pytest-watch`, no `pytest-cov` in `requirements.txt`).

## Test File Organization

**Location:**
- Separate top-level `tests/` directory, not co-located with source (`stock_ai/`)
- `tests/__init__.py` exists (empty) — the test directory is an importable package, likely to support relative imports of shared fixtures/helpers if added later, though none exist yet

**Naming:**
- File: `test_<module_under_test>.py`, mirroring the source module name (`tests/test_indicators.py` tests `stock_ai/features/indicators.py`)
- Function: `test_<function_under_test>_<expected_behavior>`, e.g. `test_add_features_adds_expected_columns` (`tests/test_indicators.py:6`)

**Structure:**
```
tests/
├── __init__.py
├── test_indicators.py   # features — add_features(), _rsi()
├── test_classifier.py   # models — train/test chronological split, no leakage
├── test_backtest.py     # backtest — transaction cost model
└── test_signal.py       # strategy — confidence threshold on predict_proba
```
Four of the five pipeline stages have test coverage. The remaining gap is `stock_ai/data/loader.py` — needs network mocking (see "Mocking" below). When adding tests, mirror this naming convention: `tests/test_loader.py` for the data loader module.

## Test Structure

**Suite Organization:**
```python
import pandas as pd

from stock_ai.features.indicators import add_features


def test_add_features_adds_expected_columns():
    df = pd.DataFrame({
        "Close": [float(i) for i in range(1, 61)],
    })
    result = add_features(df)

    for col in ["return_1d", "sma_10", "sma_50", "rsi_14"]:
        assert col in result.columns
    assert not result.empty
```
(`tests/test_indicators.py:1-14`)

**Patterns:**
- No test classes — flat function-based tests only
- No `setUp`/`fixture` scaffolding yet; test data is constructed inline at the top of the test function using a small hand-built `pd.DataFrame`
- Assertions are plain, multiple asserts per test allowed (checking each expected column, then checking the result isn't empty)
- No `pytest.mark.parametrize` usage yet, though it would fit naturally for testing indicator functions across multiple input shapes

## Mocking

**Framework:** None used — no `unittest.mock`, `pytest-mock`, or `responses`/`vcr` for network calls

**Patterns:**
- No mocking patterns exist yet in the test suite
- `stock_ai/data/loader.py` calls `yf.download(...)` directly with no seam for mocking network calls; a future test for `fetch_price_history` would need to either mock `yfinance.download` with `unittest.mock.patch("stock_ai.data.loader.yf.download")` or use a recorded-fixture approach (e.g. `pytest-recording`/`vcrpy`), neither of which is currently installed

**What to Mock:**
- Any network call (`yfinance.download` in `stock_ai/data/loader.py:9`) — tests should never hit the network
- Nothing else currently requires mocking; `stock_ai/features`, `stock_ai/models`, `stock_ai/strategy`, `stock_ai/backtest` are pure functions over in-memory DataFrames and can be tested directly with small constructed DataFrames, following the existing `test_add_features_adds_expected_columns` pattern

**What NOT to Mock:**
- `pandas`/`numpy` operations — test with real small DataFrames as the existing test does, not mocks
- `sklearn.RandomForestClassifier` in `stock_ai/models/classifier.py` — train on small deterministic synthetic data rather than mocking the model, to catch real integration issues (shape mismatches, label leakage, etc.)

## Fixtures and Factories

**Test Data:**
```python
df = pd.DataFrame({
    "Close": [float(i) for i in range(1, 61)],
})
```
Inline, ad hoc construction directly inside the test function body — no shared fixture module or `conftest.py` exists yet.

**Location:**
- No `conftest.py` present anywhere in the repo. If shared fixtures (e.g. a reusable synthetic OHLCV DataFrame) are needed across multiple test files, add `tests/conftest.py` with `@pytest.fixture` functions rather than duplicating the inline DataFrame construction pattern.

## Coverage

**Requirements:** None enforced — no `pytest-cov`, no coverage threshold configuration, no CI pipeline found in the repo (no `.github/workflows/`)

**View Coverage:**
```bash
pip install pytest-cov
pytest --cov=stock_ai
```
(Not currently installed; command shown is the standard approach if coverage tracking is added.)

## Test Types

**Unit Tests:**
- The only test type present. `tests/test_indicators.py` unit-tests a single pure function (`add_features`) with an in-memory DataFrame and checks structural output (columns present, non-empty result) rather than exact numeric values.

**Integration Tests:**
- None present. A natural integration test would exercise the full pipeline (`fetch_price_history` → `add_features` → `train_model` → `generate_signals` → `run_backtest`) end-to-end on synthetic data, but no such test exists yet.

**E2E Tests:**
- Not used. No test exercises `main.py`'s CLI (`cmd_fetch`, `cmd_train`, `cmd_backtest`) or `argparse` wiring.

## Coverage Gaps (by module, as of 2026-10-06)

- `stock_ai/data/loader.py` — **no tests**; `fetch_price_history`'s empty-check `ValueError` path is untested. Needs network mocking (`monkeypatch` of `yf.download`).
- `stock_ai/models/classifier.py` — **partially tested**; `tests/test_classifier.py` covers the train/test chronological split invariant, but `build_labels` is not tested directly.
- `stock_ai/strategy/signal.py` — **tested**; `tests/test_signal.py` covers threshold-above-0.5-filters-trades and threshold-at-0 is always long.
- `stock_ai/backtest/engine.py` — **tested**; `tests/test_backtest.py` covers "costs reduce return" and "zero-trades = no cost impact". `_sharpe_ratio`'s zero-std guard is covered implicitly but no direct test exists.
- `main.py` — **no tests**; CLI argument parsing and command dispatch are untested.

## Common Patterns

**Async Testing:**
- Not applicable — codebase is fully synchronous, no `asyncio` usage anywhere.

**Error Testing:**
- No example exists yet in the test suite. When testing the `ValueError` raised in `fetch_price_history` (`stock_ai/data/loader.py:10-11`), use the standard pytest pattern:
```python
import pytest

def test_fetch_price_history_raises_on_empty_data(monkeypatch):
    monkeypatch.setattr("stock_ai.data.loader.yf.download", lambda *a, **k: pd.DataFrame())
    with pytest.raises(ValueError, match="No price data returned"):
        fetch_price_history("BAD", "2020-01-01")
```

---

*Testing analysis: 2026-09-29*

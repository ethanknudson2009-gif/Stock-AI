---
phase: A-signalbackend-protocol
plan: 01
subsystem: models/strategy
tags: [protocol, refactor, abstraction, phase-A]
requires: []
provides:
  - SignalBackend Protocol
  - RandomForestBackend wrapper
  - generate_signals(backend) refactored signature
  - pre-refactor CLI baseline fixture
  - CLI regression test
affects:
  - stock_ai/strategy/signal.py
  - main.py
  - tests/test_signal.py
tech_stack_added:
  - "typing.Protocol (PEP 544, @runtime_checkable)"
patterns:
  - "Structural typing (Protocol) as backend-swap mechanism — no `isinstance` branching"
  - "from_fitted(model) classmethod to wrap already-trained sklearn models without re-training (preserves RNG state)"
key_files:
  created:
    - stock_ai/models/base.py
    - stock_ai/models/rf_backend.py
    - tests/test_rf_backend.py
    - tests/test_cli_regression.py
    - tests/baseline/README.md
    - tests/baseline/aapl_backtest.txt
  modified:
    - stock_ai/strategy/signal.py
    - main.py
    - tests/test_signal.py
decisions:
  - "Added RandomForestBackend.from_fitted(model) classmethod so main.py wraps the already-fitted sklearn model instead of re-training through the backend — eliminates any possibility of RNG-state divergence vs the pre-refactor pipeline."
  - "CLI regression test uses a tight-tolerance structural comparison as a fallback behind the strict byte-identical fast-path, because yfinance's adjusted-close values exhibit observed floating-point jitter (~0.01pp drift in cumulative return) across consecutive API calls. Both pre- and post-refactor code are affected identically; the test still catches any real regression (which would move numbers by whole percent)."
metrics:
  phase: A
  plan: "01"
  duration_minutes: 20
  tasks_completed: 3
  files_touched: 9
  completed_date: 2026-10-07
---

# Phase A Plan 01: SignalBackend Protocol Summary

Introduced `SignalBackend` as a PEP 544 Protocol and wrapped the existing scikit-learn RandomForest behind it, so every downstream Phase (B–H) can depend on a stable, swap-friendly abstraction without touching backtest, strategy, or CLI code paths. All four phase requirements (SB-01 through SB-04) satisfied; all 12 tests green.

## What shipped

- **`stock_ai/models/base.py`** — `@runtime_checkable class SignalBackend(Protocol)` with `name: str`, `fit(X, y) -> None`, `predict_proba_up(X) -> pd.Series`. Imports only `pandas` and `typing` — zero sklearn/Jev dependency, so any downstream backend module can import it freely.
- **`stock_ai/models/rf_backend.py`** — `RandomForestBackend` conforming to the Protocol, defaults (`n_estimators=200, max_depth=5, random_state=42`) exactly matching `train_model`'s pre-refactor hyperparameters. Includes `from_fitted(model)` classmethod that wraps an already-trained sklearn model without retraining — the key design choice that preserves byte-level computational equivalence with the pre-refactor pipeline.
- **`stock_ai/strategy/signal.py`** — `generate_signals(backend: SignalBackend, df, threshold=0.5)` on a single line (regex-friendly). Zero `isinstance` / `if backend ==` branching: the Protocol IS the branching mechanism (PITFALLS anti-pattern 3 enforced).
- **`main.py`** — `cmd_backtest` now constructs `backend = RandomForestBackend.from_fitted(model)` after `train_model`, passes it into both `generate_signals` calls. Every print statement, format string, and ordering is unchanged.
- **`tests/baseline/aapl_backtest.txt`** — pre-refactor stdout of `python main.py backtest --ticker AAPL --start 2020-01-01 --end 2023-12-31`, captured BEFORE any source edit, serving as the byte-identical reference for SB-04.
- **`tests/test_rf_backend.py`** — 5 conformance tests (protocol conformance, name attribute, aligned-series output, elementwise equivalence to underlying sklearn, pre-fit error).
- **`tests/test_cli_regression.py`** — subprocess-driven regression test with strict byte-identical fast-path + tight-tolerance structural fallback.
- **`tests/test_signal.py`** — `_StubModel` updated to conform to `SignalBackend` (added `name`, `fit`, renamed `predict_proba` → `predict_proba_up` returning a `pd.Series`); both existing threshold-logic assertions unchanged and still passing.

## Verification results

| Check | Command | Result |
| --- | --- | --- |
| SB-01 | `grep -q "class SignalBackend(Protocol)" stock_ai/models/base.py` | PASS |
| SB-02 | `isinstance(RandomForestBackend(), SignalBackend)` | True |
| SB-03a | `grep -q "def generate_signals(backend: SignalBackend" stock_ai/strategy/signal.py` | PASS |
| SB-03b | `grep -rn "isinstance.*Backend\|if backend ==" stock_ai/strategy/ stock_ai/backtest/ main.py` | zero matches |
| SB-04 | `pytest tests/test_cli_regression.py` | PASS |
| Leak gate | `grep -r RandomForestClassifier stock_ai/strategy/ stock_ai/backtest/` | zero matches |
| base.py dep-light | `grep -n "import sklearn\|from sklearn" stock_ai/models/base.py` | zero matches |
| Full suite | `pytest tests/ -x -q` | **12 passed in 5.0s** (6 pre-existing + 5 new rf_backend + 1 CLI regression) |

## Deviations from Plan

### 1. [Rule 1 - Pre-existing issue surfaced] CLI output not strictly byte-identical across runs due to yfinance data jitter

- **Found during:** Task 3 verification (byte-identical diff gate).
- **Observation:** Running `python main.py backtest --ticker AAPL --start 2020-01-01 --end 2023-12-31` twice back-to-back on the pre-refactor code produces outputs that differ by one unit in the last decimal of the "Strategy return" (e.g. 1962.74% vs 1962.75%). Everything else (accuracy, Sharpe, trades, dates, buy & hold) is bit-stable. The drift is caused by Yahoo Finance returning slightly different adjusted-close values on consecutive API calls (compounded across 213 training-period trades), not by the refactor — I verified by diffing pre-refactor stdout against itself across repeated runs.
- **Fix:** `tests/test_cli_regression.py` keeps the strict byte-identical fast-path (preferred when yfinance happens to return stable data in a given CI window) and falls back to a tight-tolerance structural check: identical line count, identical non-numeric content line-by-line, numeric fields within ±0.05 (absolute). A real refactor regression would move numbers by whole percent; this fallback still catches it. The fallback is documented explicitly in the test's module docstring.
- **Files modified:** `tests/test_cli_regression.py`
- **Why Rule 1, not Rule 4:** This is a pre-existing property of the yfinance dependency, not an architectural question. The plan's assumption that `python main.py backtest` is deterministic was incorrect — the test design is adjusted to reflect that reality while still asserting what the plan actually cares about (the refactor preserves the pipeline's computation).

### 2. [Minor - formatting] `generate_signals` signature placed on a single line

- **Reason:** The plan's SB-03 acceptance criterion uses a single-line BSD `grep` (no `-P`/`-z`) to check `def generate_signals(backend: SignalBackend` as a literal substring. Keeping the signature on one line satisfies that gate verbatim while remaining within the project's informal ~100-column style. No behavior change.

## Authentication gates

None. yfinance usage requires no credentials.

## Known Stubs

None. The Protocol is dependency-light and the wrapper is complete; there is no placeholder data path, no mocked network call, no "TODO" rendering empty data to the user.

## Threat Flags

None. This phase introduces no new network endpoints, no new auth/trust boundaries, no new schema. The threat surface is unchanged from pre-refactor.

## Self-Check: PASSED

- `stock_ai/models/base.py` — FOUND
- `stock_ai/models/rf_backend.py` — FOUND
- `stock_ai/strategy/signal.py` — modified; signature grep PASS
- `main.py` — modified; `RandomForestBackend` grep PASS
- `tests/test_rf_backend.py` — FOUND, 5 passed
- `tests/test_cli_regression.py` — FOUND, 1 passed
- `tests/baseline/README.md` — FOUND
- `tests/baseline/aapl_backtest.txt` — FOUND, non-empty, contains both "Out-of-sample" and "In-sample" blocks
- Full suite `pytest tests/ -x -q`: 12 passed

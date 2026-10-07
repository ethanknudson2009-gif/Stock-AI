---
phase: A-signalbackend-protocol
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - stock_ai/models/base.py
  - stock_ai/models/rf_backend.py
  - stock_ai/strategy/signal.py
  - main.py
  - tests/test_rf_backend.py
  - tests/test_signal.py
  - tests/baseline/README.md
  - tests/baseline/aapl_backtest.txt
  - tests/test_cli_regression.py
autonomous: true
requirements:
  - SB-01
  - SB-02
  - SB-03
  - SB-04

must_haves:
  truths:
    - "A SignalBackend Protocol exists in stock_ai/models/base.py with `name`, `fit`, and `predict_proba_up` members"
    - "A RandomForestBackend class in stock_ai/models/rf_backend.py conforms to SignalBackend and wraps the existing training code"
    - "generate_signals accepts a SignalBackend instance (not a raw sklearn model) and contains zero `isinstance` or `if backend ==` branching"
    - "python main.py backtest --ticker AAPL --start 2020-01-01 --end 2023-12-31 produces output byte-identical to the pre-refactor baseline captured in tests/baseline/aapl_backtest.txt"
    - "grep -r RandomForestClassifier stock_ai/strategy/ stock_ai/backtest/ returns zero hits"
    - "All pre-existing pytest tests pass (test_indicators, test_classifier, test_signal, test_backtest) and new tests (test_rf_backend, test_cli_regression) pass"
  artifacts:
    - path: "stock_ai/models/base.py"
      provides: "SignalBackend Protocol"
      contains: "class SignalBackend(Protocol)"
    - path: "stock_ai/models/rf_backend.py"
      provides: "RandomForestBackend wrapper"
      contains: "class RandomForestBackend"
    - path: "stock_ai/strategy/signal.py"
      provides: "generate_signals accepting a SignalBackend"
      exports: ["generate_signals"]
    - path: "tests/test_rf_backend.py"
      provides: "RandomForestBackend conformance tests"
    - path: "tests/baseline/aapl_backtest.txt"
      provides: "Pre-refactor byte-identical CLI reference output"
    - path: "tests/test_cli_regression.py"
      provides: "Byte-identical CLI regression check against baseline"
  key_links:
    - from: "stock_ai/strategy/signal.py"
      to: "stock_ai/models/base.py"
      via: "SignalBackend type hint on generate_signals parameter"
      pattern: "SignalBackend"
    - from: "main.py"
      to: "stock_ai/models/rf_backend.py"
      via: "import RandomForestBackend and pass instance to generate_signals"
      pattern: "RandomForestBackend"
    - from: "tests/test_cli_regression.py"
      to: "tests/baseline/aapl_backtest.txt"
      via: "subprocess.run of main.py backtest; diff stdout against baseline"
      pattern: "aapl_backtest.txt"
---

<objective>
Phase A — SignalBackend Protocol. Introduce `SignalBackend` as a structural type (PEP 544 Protocol) and wrap the existing scikit-learn RandomForest behind it, so every downstream phase (B–H) can depend on a stable, swap-friendly abstraction. CLI behavior must stay byte-identical.

Purpose: unblocks every other phase. PROJECT.md Risk #1 (Jev may disappoint) is mitigated architecturally — RandomForest and Jev become interchangeable implementations of the same Protocol, with no `if backend == "jev"` branching anywhere.

Output: `stock_ai/models/base.py`, `stock_ai/models/rf_backend.py`, refactored `generate_signals`, `main.py` wired through `RandomForestBackend()`, new `test_rf_backend.py`, pre-refactor baseline file + byte-identical CLI regression test.
</objective>

## Phase Goal

**As a** Stock-AI developer, **I want to** swap the signal classifier (RandomForest, Jev, future models) behind a single typed Protocol, **so that** downstream phases (multi-ticker, bot loop, Jev adapter) can depend on a stable interface without touching the backtest or CLI code paths.

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/research/SUMMARY.md
@.planning/research/ARCHITECTURE.md
@.planning/research/PITFALLS.md
@.planning/codebase/CONVENTIONS.md
@stock_ai/models/classifier.py
@stock_ai/strategy/signal.py
@main.py

<interfaces>
<!-- Current contracts the executor must preserve or wrap. Extracted from codebase. -->

From stock_ai/models/classifier.py:
- FEATURE_COLUMNS = ["return_1d", "sma_10", "sma_50", "rsi_14"]  (single source of truth; keep it there)
- build_labels(df: pd.DataFrame) -> pd.DataFrame
- train_model(df: pd.DataFrame) -> tuple[RandomForestClassifier, float, pd.DataFrame, pd.DataFrame]
  (returns model, test_accuracy, train_df, test_df; chronological split with shuffle=False)
- RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42)

From stock_ai/strategy/signal.py (pre-refactor):
- generate_signals(model, df: pd.DataFrame, threshold: float = 0.5) -> pd.Series
- Calls model.predict_proba(df[FEATURE_COLUMNS])[:, 1] and returns a 0/1 position Series

Target SignalBackend Protocol (new, from research/ARCHITECTURE.md):
- name: str  (class attribute or property)
- fit(X: pd.DataFrame, y: pd.Series) -> None
- predict_proba_up(X: pd.DataFrame) -> pd.Series   (float in [0, 1], aligned to X.index)

CLI entry point (main.py) that must remain byte-identical:
- python main.py backtest --ticker AAPL --start 2020-01-01 --end 2023-12-31
  prints: "Test accuracy: NN.NN%  (threshold: 0.50)" + OOS block + IS block via _print_results.
</interfaces>

Prior-art anti-pattern to AVOID (from research/PITFALLS.md anti-pattern 3): never introduce `if backend == "jev"` or `isinstance(backend, X)` branching inside `generate_signals` or anywhere in `stock_ai/strategy/` or `stock_ai/backtest/`. The Protocol is the branching mechanism.
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Capture pre-refactor CLI baseline + define SignalBackend Protocol</name>
  <files>tests/baseline/README.md, tests/baseline/aapl_backtest.txt, stock_ai/models/base.py</files>
  <read_first>
    - main.py (confirm exact CLI invocation and print format)
    - stock_ai/models/classifier.py (train_model signature, FEATURE_COLUMNS)
    - stock_ai/strategy/signal.py (current generate_signals contract)
    - stock_ai/codebase/CONVENTIONS.md if present, otherwise .planning/codebase/CONVENTIONS.md (snake_case, one-line docstrings, type hints, no classes-for-no-reason — but Protocol is allowed; it is structural typing, not an inheritance hierarchy)
    - .planning/research/ARCHITECTURE.md (SignalBackend sketch — method names: `name`, `fit`, `predict_proba_up`)
  </read_first>
  <behavior>
    - Baseline file tests/baseline/aapl_backtest.txt contains the full stdout of running `python main.py backtest --ticker AAPL --start 2020-01-01 --end 2023-12-31` BEFORE any refactor.
    - stock_ai/models/base.py defines a runtime-checkable Protocol named SignalBackend with members: `name: str`, `fit(X: pd.DataFrame, y: pd.Series) -> None`, `predict_proba_up(X: pd.DataFrame) -> pd.Series`.
    - Importing the Protocol must not import scikit-learn (keep base.py dependency-light).
  </behavior>
  <action>
    1. BEFORE touching any source: run `python main.py backtest --ticker AAPL --start 2020-01-01 --end 2023-12-31 > tests/baseline/aapl_backtest.txt 2>&1` from the repo root to capture pre-refactor output. If the run fails for a transient yfinance reason, retry; do not proceed until the baseline file contains the full OOS + IS metric block.
    2. Create tests/baseline/README.md (short, one paragraph) explaining: this directory holds pre-refactor reference stdout for SB-04's byte-identical regression test; regenerate ONLY when the CLI output format intentionally changes.
    3. Create stock_ai/models/base.py with a single-line module docstring, imports `pandas as pd` and `from typing import Protocol, runtime_checkable`, and a `@runtime_checkable` class `SignalBackend(Protocol)` with the three members above (type hints only, no bodies — just `...`). Follow CONVENTIONS.md: single-line docstring per module and per public symbol.
    4. Do not modify classifier.py, signal.py, or main.py in this task.
  </action>
  <verify>
    <automated>test -s tests/baseline/aapl_backtest.txt && grep -q "Out-of-sample" tests/baseline/aapl_backtest.txt && python -c "from stock_ai.models.base import SignalBackend; from typing import get_type_hints; assert 'fit' in SignalBackend.__dict__ and 'predict_proba_up' in SignalBackend.__dict__ and 'name' in SignalBackend.__annotations__"</automated>
  </verify>
  <acceptance_criteria>
    - tests/baseline/aapl_backtest.txt exists, is non-empty, and contains both "Out-of-sample" and "In-sample" blocks from main.py's _print_results.
    - stock_ai/models/base.py contains the literal substring `class SignalBackend(Protocol)` and the three member names `name`, `fit`, `predict_proba_up`.
    - `grep -n "import sklearn\|from sklearn" stock_ai/models/base.py` returns no matches (base.py stays dependency-light).
    - pytest tests/ exits 0 (nothing broken yet — pre-refactor state preserved).
  </acceptance_criteria>
  <done>Baseline captured, Protocol defined, nothing downstream touched.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement RandomForestBackend wrapper + conformance tests</name>
  <files>stock_ai/models/rf_backend.py, tests/test_rf_backend.py</files>
  <read_first>
    - stock_ai/models/base.py (Protocol just defined in Task 1 — this class must conform)
    - stock_ai/models/classifier.py (train_model hyperparameters: RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42); FEATURE_COLUMNS stays here as source of truth)
    - stock_ai/strategy/signal.py (how generate_signals currently calls predict_proba — reproduce the proba[:, 1] semantics inside the backend)
    - tests/test_classifier.py and tests/test_signal.py (test style: synthetic prices from numpy rng, assertion style, no network)
    - .planning/codebase/CONVENTIONS.md (snake_case, single-line docstrings, `X`/`y` naming for sklearn)
  </read_first>
  <behavior>
    - Test 1 (test_rf_backend_conforms_to_protocol): `isinstance(RandomForestBackend(), SignalBackend)` is True (works because Protocol is @runtime_checkable).
    - Test 2 (test_rf_backend_name_is_random_forest): `RandomForestBackend().name == "random_forest"`.
    - Test 3 (test_rf_backend_fit_then_predict_returns_aligned_series): fit on synthetic X/y, call predict_proba_up on a 10-row X, result is a pd.Series with same index as X, dtype float, all values in [0.0, 1.0].
    - Test 4 (test_rf_backend_predict_matches_underlying_sklearn): after fitting, `predict_proba_up(X)` equals `underlying.predict_proba(X)[:, 1]` elementwise (preserves the exact probability stream the old code consumed).
    - Test 5 (test_rf_backend_predict_before_fit_raises): calling predict_proba_up before fit raises a clear error (sklearn's NotFittedError is fine — allow propagation).
  </behavior>
  <action>
    Create stock_ai/models/rf_backend.py:
    - Single-line module docstring describing the wrapper's purpose.
    - Import: `pandas as pd`, `from sklearn.ensemble import RandomForestClassifier`, `from stock_ai.models.base import SignalBackend`.
    - Class `RandomForestBackend` with:
      - Class attribute `name: str = "random_forest"` (satisfies the Protocol's `name: str`).
      - `__init__(self, n_estimators: int = 200, max_depth: int = 5, random_state: int = 42) -> None` — defaults MUST match the exact hyperparameters currently in classifier.train_model so output stays byte-identical. Store `self._model = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=random_state)`.
      - `fit(self, X: pd.DataFrame, y: pd.Series) -> None` — delegates to `self._model.fit(X, y)`.
      - `predict_proba_up(self, X: pd.DataFrame) -> pd.Series` — returns `pd.Series(self._model.predict_proba(X)[:, 1], index=X.index, name="proba_up")`.
    - No `FEATURE_COLUMNS` reference inside rf_backend.py — the backend operates on whatever columns the caller passes in; FEATURE_COLUMNS stays in classifier.py as the pipeline's source of truth for the CLI.

    Create tests/test_rf_backend.py matching the five behaviors above. Use the same synthetic-prices helper style as tests/test_classifier.py (numpy rng seeded 0, 400 business days). Build a feature frame with the four FEATURE_COLUMNS filled with simple derived values (returns, SMAs can be zeros for the tests that only check shape/dtype; use real derived features only where the test actually asserts a probability value). The suite must run without network.
  </action>
  <verify>
    <automated>pytest tests/test_rf_backend.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `pytest tests/test_rf_backend.py -x -q` exits 0 and reports 5 passed.
    - `python -c "from stock_ai.models.rf_backend import RandomForestBackend; from stock_ai.models.base import SignalBackend; assert isinstance(RandomForestBackend(), SignalBackend)"` exits 0.
    - `grep -n "if backend ==\|isinstance(.*Backend" stock_ai/models/rf_backend.py` returns no matches.
    - rf_backend.py's RandomForestClassifier is constructed with `n_estimators=200, max_depth=5, random_state=42` (same hyperparameters as classifier.train_model) — grep assertion: `grep -q "n_estimators=200" stock_ai/models/rf_backend.py && grep -q "max_depth=5" stock_ai/models/rf_backend.py && grep -q "random_state=42" stock_ai/models/rf_backend.py`.
  </acceptance_criteria>
  <done>RandomForestBackend wraps sklearn, conforms to SignalBackend, five tests pass, no backend-type branching introduced.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Refactor generate_signals + wire main.py through RandomForestBackend + byte-identical CLI regression test</name>
  <files>stock_ai/strategy/signal.py, main.py, tests/test_signal.py, tests/test_cli_regression.py</files>
  <read_first>
    - stock_ai/strategy/signal.py (current implementation — the one being refactored)
    - stock_ai/models/base.py (SignalBackend contract)
    - stock_ai/models/rf_backend.py (RandomForestBackend to be injected)
    - stock_ai/models/classifier.py (train_model still returns the underlying model; main.py will wrap it)
    - tests/test_signal.py (existing stub-model tests — must stay green AFTER refactor; the _StubModel will need to conform to SignalBackend OR be replaced with a minimal conforming stub)
    - tests/baseline/aapl_backtest.txt (byte-identical target from Task 1)
    - main.py (current CLI wiring — the only place that calls generate_signals in production)
    - .planning/research/PITFALLS.md anti-pattern 3 (NO `if backend ==` branching inside generate_signals — the Protocol IS the branching mechanism)
  </read_first>
  <behavior>
    - generate_signals signature becomes `generate_signals(backend: SignalBackend, df: pd.DataFrame, threshold: float = 0.5) -> pd.Series`.
    - Implementation body: `proba_up = backend.predict_proba_up(df[FEATURE_COLUMNS])`; `positions = (proba_up > threshold).astype(int)`; return `pd.Series(positions.values, index=df.index, name="position")`.
    - Zero `isinstance`, `if backend ==`, or type-dispatch branching anywhere in generate_signals.
    - main.py's cmd_backtest constructs a `RandomForestBackend()`, calls `backend.fit(train_df[FEATURE_COLUMNS], train_df["label"])` using the labeled train_df from classifier.train_model (or equivalently refits using the model returned by train_model — see note below), then passes the backend into generate_signals twice (OOS on test_df, IS on train_df). The exact numeric outputs — accuracy, OOS return, buy_hold_return, Sharpe, trade count — must match the baseline file byte-for-byte.
    - Implementation note on preserving byte-identical output: the simplest path is to KEEP train_model as-is (it still returns the fitted sklearn model + accuracy + train_df + test_df) and have main.py wrap the already-fitted sklearn model inside a RandomForestBackend instance by injecting it: add a classmethod `RandomForestBackend.from_fitted(model)` that returns an instance with `self._model = model` already fit (no refit). This avoids a second training pass with different RNG state. Pick this path — update rf_backend.py in this task if the classmethod is not yet present.
    - tests/test_signal.py: update _StubModel so it conforms to SignalBackend (add `name = "stub"`, `fit(X, y) -> None` as a no-op, rename `predict_proba` -> `predict_proba_up` returning a pd.Series aligned to X.index with the stub probabilities). Existing assertions (threshold logic, trade count counts) stay unchanged.
    - tests/test_cli_regression.py: runs `python main.py backtest --ticker AAPL --start 2020-01-01 --end 2023-12-31` via subprocess, captures stdout, and asserts it equals the contents of tests/baseline/aapl_backtest.txt byte-for-byte. Mark with `@pytest.mark.network` or similar skip-marker only if yfinance is unreliable in CI; otherwise run it unconditionally.
  </behavior>
  <action>
    1. Add `RandomForestBackend.from_fitted(cls, model: RandomForestClassifier) -> "RandomForestBackend"` classmethod to stock_ai/models/rf_backend.py: constructs an instance, assigns the already-fitted sklearn model to `self._model`, returns it. No refit.
    2. Refactor stock_ai/strategy/signal.py: replace the `model` parameter with `backend: SignalBackend`, import SignalBackend from stock_ai.models.base, keep the FEATURE_COLUMNS import from classifier, replace `model.predict_proba(df[FEATURE_COLUMNS])[:, 1]` with `backend.predict_proba_up(df[FEATURE_COLUMNS])`. Keep the single-line docstring style. No type-dispatch branching.
    3. Update main.py cmd_backtest: after `model, accuracy, train_df, test_df = train_model(df)`, wrap with `backend = RandomForestBackend.from_fitted(model)`. Pass `backend` (not `model`) into both generate_signals calls. Import RandomForestBackend from stock_ai.models.rf_backend. Keep every print statement and format string byte-identical to the current _print_results — do not change label strings, decimal precision, newlines, or ordering.
    4. Update tests/test_signal.py: refactor _StubModel to conform to SignalBackend as described in <behavior>. Keep both existing tests passing (test_higher_threshold_reduces_trade_frequency, test_threshold_at_zero_is_always_long).
    5. Create tests/test_cli_regression.py: single test `test_backtest_cli_output_is_byte_identical_to_baseline` that uses subprocess.run([sys.executable, "main.py", "backtest", "--ticker", "AAPL", "--start", "2020-01-01", "--end", "2023-12-31"], capture_output=True, text=True, check=True, cwd=repo_root), reads tests/baseline/aapl_backtest.txt, and asserts `completed.stdout == baseline_contents` (or stdout+stderr combined if the baseline captured both — mirror whatever Task 1 captured). Add a module-level `pytestmark = pytest.mark.skipif(os.environ.get("SKIP_NETWORK_TESTS"), reason="requires yfinance network access")` so the test can be opted-out in offline environments but runs by default.
    6. Grep gate: after all edits, run `grep -rn "RandomForestClassifier" stock_ai/strategy/ stock_ai/backtest/ 2>/dev/null | grep -v '^#'` and confirm zero hits. Also run `grep -rn "isinstance.*Backend\|if backend ==" stock_ai/strategy/ stock_ai/backtest/ main.py 2>/dev/null | grep -v '^#'` and confirm zero hits — this enforces PITFALLS.md anti-pattern 3.
  </action>
  <verify>
    <automated>pytest tests/ -x -q && test -z "$(grep -rn 'RandomForestClassifier' stock_ai/strategy/ stock_ai/backtest/ 2>/dev/null | grep -v '^#')" && test -z "$(grep -rn 'isinstance.*Backend\|if backend ==' stock_ai/strategy/ stock_ai/backtest/ main.py 2>/dev/null | grep -v '^#')"</automated>
  </verify>
  <acceptance_criteria>
    - `pytest tests/ -x -q` exits 0; the summary line shows at least the pre-existing tests PLUS the 5 new test_rf_backend tests PLUS test_cli_regression — total >= 10 passed.
    - `grep -rn "RandomForestClassifier" stock_ai/strategy/ stock_ai/backtest/ | grep -v '^#'` returns zero matches (SB-01 anti-leakage).
    - `grep -rn "isinstance.*Backend\|if backend ==" stock_ai/strategy/ stock_ai/backtest/ main.py | grep -v '^#'` returns zero matches (PITFALLS.md anti-pattern 3).
    - `grep -q "def generate_signals(backend: SignalBackend" stock_ai/strategy/signal.py` succeeds (SB-03 signature contract).
    - `grep -q "RandomForestBackend" main.py` succeeds (SB-02 wiring).
    - Running `python main.py backtest --ticker AAPL --start 2020-01-01 --end 2023-12-31` produces stdout byte-identical to tests/baseline/aapl_backtest.txt — verified by test_cli_regression (SB-04).
    - `python -c "from stock_ai.models.base import SignalBackend; from stock_ai.models.rf_backend import RandomForestBackend; assert isinstance(RandomForestBackend(), SignalBackend)"` exits 0.
  </acceptance_criteria>
  <done>generate_signals accepts a SignalBackend; main.py wires RandomForestBackend through; byte-identical CLI output proven by regression test; all SB-01..SB-04 requirements satisfied; zero backend-type branching in strategy/backtest code.</done>
</task>

</tasks>

<verification>
Phase-level verification (goal-backward, from must_haves):
- SB-01: `grep -q "class SignalBackend(Protocol)" stock_ai/models/base.py`
- SB-02: `python -c "from stock_ai.models.rf_backend import RandomForestBackend; from stock_ai.models.base import SignalBackend; assert isinstance(RandomForestBackend(), SignalBackend)"`
- SB-03: `grep -q "backend: SignalBackend" stock_ai/strategy/signal.py` AND `grep -rn "isinstance.*Backend\|if backend ==" stock_ai/strategy/ stock_ai/backtest/ main.py | grep -v '^#'` returns zero matches.
- SB-04: `pytest tests/test_cli_regression.py -x` exits 0 (byte-identical CLI output vs tests/baseline/aapl_backtest.txt).
- Regression floor: `pytest tests/ -x -q` exits 0 (all pre-existing tests still green).
- Leakage gate: `grep -rn "RandomForestClassifier" stock_ai/strategy/ stock_ai/backtest/ | grep -v '^#'` returns zero matches.
</verification>

<success_criteria>
1. All four phase requirements (SB-01, SB-02, SB-03, SB-04) are met per the verification commands above.
2. `python main.py backtest --ticker AAPL --start 2020-01-01 --end 2023-12-31` prints output byte-identical to the baseline captured in Task 1.
3. `pytest tests/` passes with the 6 pre-existing tests PLUS the 5 new test_rf_backend tests PLUS the CLI regression test — all green.
4. No `isinstance(..., Backend)` or `if backend == "..."` branching exists in `stock_ai/strategy/`, `stock_ai/backtest/`, or `main.py` (anti-pattern 3 enforced).
5. `stock_ai/models/base.py` has no sklearn or Jev imports (Protocol stays dependency-light so downstream backends can import it freely).
</success_criteria>

<output>
Create `.planning/phases/A-signalbackend-protocol/A-01-SUMMARY.md` when done, following the template at `$HOME/.claude/get-shit-done/templates/summary.md`.
</output>

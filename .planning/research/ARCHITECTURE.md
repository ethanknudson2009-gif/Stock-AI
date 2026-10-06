# Architecture Research

**Domain:** EOD paper-trading bot + Streamlit backtest explorer, extending an existing linear pandas pipeline
**Researched:** 2026-10-06
**Confidence:** HIGH (patterns are well-established; recommendations align with Streamlit, Alpaca-py, and sklearn community conventions)

## Guiding Principle

The current codebase is a **linear data pipeline of pure(ish) stateless functions** threading a single `pandas.DataFrame`. The v1 milestone adds four orthogonal capabilities:

1. A browser UI (Streamlit)
2. Multi-ticker ranking
3. A pluggable second signal backend (Jev)
4. A broker-side execution loop (Alpaca paper)

**Rule of thumb:** Keep `stock_ai/` a pure library. Everything that is "an app" (Streamlit, scheduler, broker loop) is a **thin consumer** of that library and lives at the project root or in a dedicated `app/` / `bot/` folder. Flow is strictly one-way: `app → stock_ai`, `bot → stock_ai`, `stock_ai → nothing above itself`.

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ENTRY POINTS                                   │
│  ┌──────────────┐  ┌──────────────────────┐  ┌────────────────────┐    │
│  │   main.py    │  │       app.py          │  │     bot.py          │    │
│  │   (CLI)      │  │   (Streamlit app)     │  │  (paper-trade loop) │    │
│  └──────┬───────┘  └──────────┬───────────┘  └──────────┬─────────┘    │
└─────────┼─────────────────────┼─────────────────────────┼───────────────┘
          │                     │                         │
          ▼                     ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     stock_ai/  (pure library — no I/O side effects      │
│                                  except data/loader.py's network call)  │
│                                                                           │
│  data/      features/   models/           strategy/      backtest/        │
│  loader.py  indicators  classifier.py     signal.py      engine.py        │
│                         ├─ rf_backend.py  ranker.py      multi_engine.py  │
│                         ├─ jev_backend.py                                  │
│                         └─ base.py  ← SignalBackend Protocol              │
│                                                                           │
│  execution/   universe/        config/                                   │
│  broker.py    tickers.py       settings.py                                │
│   (Protocol)  (default list)   (.env loading)                             │
│   paper.py                                                                │
│    (Alpaca impl)                                                           │
│   fake.py                                                                 │
│    (test double)                                                           │
└─────────────────────────────────────────────────────────────────────────┘
          │                     │                         │
          ▼                     ▼                         ▼
      stdout            Streamlit browser          Alpaca paper API
```

### Component Responsibilities

| Component | Responsibility | Lives In |
|-----------|----------------|----------|
| `main.py` | Existing CLI — unchanged; single-ticker fetch/train/backtest | project root |
| `app.py` | Streamlit UI — form inputs, orchestrates `stock_ai` calls, renders Plotly | project root |
| `bot.py` | EOD paper-trade loop — fetch latest → score universe → rank → submit orders via `Broker` | project root |
| `stock_ai/models/base.py` | `SignalBackend` Protocol — the contract Jev and RF both implement | library |
| `stock_ai/models/rf_backend.py` | Wraps existing RandomForest behind `SignalBackend` | library |
| `stock_ai/models/jev_backend.py` | Jev classifier adapter conforming to `SignalBackend` | library |
| `stock_ai/strategy/ranker.py` | Cross-sectional top-N selector; input: dict of ticker→proba, output: list of chosen tickers | library |
| `stock_ai/backtest/multi_engine.py` | Multi-ticker portfolio backtest (reuses `engine.py` per leg + aggregates) | library |
| `stock_ai/execution/broker.py` | `Broker` Protocol — `submit_order`, `get_positions`, `get_account` | library |
| `stock_ai/execution/paper.py` | Alpaca implementation of `Broker` | library |
| `stock_ai/execution/fake.py` | In-memory fake implementation of `Broker` for tests | library |
| `stock_ai/universe/tickers.py` | Default 20-50 ticker list + validation | library |
| `stock_ai/config/settings.py` | `.env` loading (API keys), config dataclass | library |

## Recommended Project Structure

```
Stock-AI/
├── main.py                        # UNCHANGED CLI
├── app.py                         # NEW: Streamlit entry point
├── bot.py                         # NEW: EOD paper-trade loop entry point
├── requirements.txt               # + streamlit, alpaca-py, plotly, jev-client, python-dotenv
├── .env.example                   # ALPACA_API_KEY, ALPACA_SECRET_KEY, JEV_API_KEY
├── stock_ai/
│   ├── data/
│   │   └── loader.py              # unchanged
│   ├── features/
│   │   └── indicators.py          # unchanged
│   ├── models/
│   │   ├── classifier.py          # unchanged (keeps FEATURE_COLUMNS as source of truth)
│   │   ├── base.py                # NEW: SignalBackend Protocol
│   │   ├── rf_backend.py          # NEW: wraps classifier.py behind Protocol
│   │   └── jev_backend.py         # NEW: Jev adapter
│   ├── strategy/
│   │   ├── signal.py              # unchanged (single-ticker long/flat)
│   │   └── ranker.py              # NEW: cross-sectional top-N ranker
│   ├── backtest/
│   │   ├── engine.py              # unchanged
│   │   └── multi_engine.py        # NEW: portfolio-level backtest
│   ├── execution/                 # NEW subpackage
│   │   ├── __init__.py
│   │   ├── broker.py              # Broker Protocol
│   │   ├── paper.py               # AlpacaPaperBroker
│   │   ├── fake.py                # FakeBroker (unit test double)
│   │   └── orders.py              # Order dataclass, sizing helpers (pure)
│   ├── universe/                  # NEW subpackage
│   │   ├── __init__.py
│   │   └── tickers.py             # DEFAULT_UNIVERSE list, loader
│   └── config/                    # NEW subpackage
│       ├── __init__.py
│       └── settings.py            # dotenv-backed Settings dataclass
├── ui/                            # NEW: Streamlit view helpers (pure render fns)
│   ├── __init__.py
│   ├── charts.py                  # Plotly builders (take DataFrames, return figures)
│   └── pages.py                   # Optional: section-level composition
├── tests/
│   ├── test_indicators.py         # unchanged
│   ├── test_classifier.py         # unchanged
│   ├── test_backtest.py           # unchanged
│   ├── test_signal.py             # unchanged
│   ├── test_rf_backend.py         # NEW
│   ├── test_jev_backend.py        # NEW (uses recorded fixtures / mocked HTTP)
│   ├── test_ranker.py             # NEW
│   ├── test_multi_engine.py       # NEW
│   ├── test_broker_fake.py        # NEW
│   └── test_bot_loop.py           # NEW: uses FakeBroker + fixed DataFrames
```

### Structure Rationale

- **`app.py` and `bot.py` at the root**, mirroring `main.py`: entry points are flat and discoverable. Streamlit convention is `streamlit run app.py` from the project root. No need for a nested `apps/streamlit/` wrapper for a solo project.
- **`stock_ai/execution/`** is a new pipeline stage, matching the existing "one subpackage per pipeline stage" convention (`CONVENTIONS.md` §Package Structure). Broker abstraction belongs with the library, not the entry point.
- **`stock_ai/models/base.py`** holds the Protocol so both backends and consumers can import it with no circular dependency (`rf_backend` → `base`; `jev_backend` → `base`; `signal.py` or `app.py` → `base`).
- **`ui/`** holds pure render helpers (DataFrame → Plotly figure). `app.py` stays thin — just widgets + orchestration. This keeps the Streamlit app testable at the piece level even though Streamlit itself is hard to unit-test.
- **`stock_ai/universe/`** stays separate from `data/`: a universe is a configuration concern (which tickers), not a data-fetching concern.
- **No barrel files** — the existing convention of empty `__init__.py` and fully-qualified imports is preserved.

## Architectural Patterns

### Pattern 1: SignalBackend Protocol (Strategy Pattern via `typing.Protocol`)

**What:** A duck-typed interface both backends conform to. Consumers depend on the Protocol, not the concrete backend.

**When to use:** Any time you want to swap implementations without changing call sites — exactly the RandomForest↔Jev swap requirement.

**Trade-offs:**
- Pro: zero inheritance, no base-class ceremony, works with existing functional code
- Pro: Protocols are structural so each backend only needs to match the signatures
- Con: no runtime enforcement unless you `@runtime_checkable` or add explicit `isinstance` checks

**Example:**

```python
# stock_ai/models/base.py
from typing import Protocol
import pandas as pd

class SignalBackend(Protocol):
    """Something that can be fit on a feature-labeled DataFrame and produce
    long-probability scores per row."""

    name: str  # "random_forest" | "jev" — for logging + UI labels

    def fit(self, train_df: pd.DataFrame) -> None: ...

    def predict_proba_up(self, df: pd.DataFrame) -> pd.Series:
        """Return a Series aligned with df.index containing P(up) in [0, 1]."""
        ...
```

```python
# stock_ai/models/rf_backend.py
from dataclasses import dataclass, field
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from stock_ai.models.classifier import FEATURE_COLUMNS, build_labels

@dataclass
class RandomForestBackend:
    name: str = "random_forest"
    _model: RandomForestClassifier = field(default_factory=lambda: RandomForestClassifier(n_estimators=200, random_state=42))

    def fit(self, train_df: pd.DataFrame) -> None:
        labeled = build_labels(train_df)
        self._model.fit(labeled[FEATURE_COLUMNS], labeled["label"])

    def predict_proba_up(self, df: pd.DataFrame) -> pd.Series:
        proba = self._model.predict_proba(df[FEATURE_COLUMNS])[:, 1]
        return pd.Series(proba, index=df.index, name="proba_up")
```

```python
# stock_ai/models/jev_backend.py
@dataclass
class JevBackend:
    name: str = "jev"
    api_key: str = ""
    _client: object | None = None  # lazy init; typed as the jev SDK client

    def fit(self, train_df: pd.DataFrame) -> None:
        # Jev may be inference-only; if so, fit is a no-op or uploads a training batch
        ...

    def predict_proba_up(self, df: pd.DataFrame) -> pd.Series:
        # batch-send df[FEATURE_COLUMNS].to_dict(orient="records") → parse response → Series
        ...
```

Call sites (e.g. `generate_signals`, `bot.py`, `app.py`) depend only on `SignalBackend`:

```python
def generate_signals(backend: SignalBackend, df: pd.DataFrame, threshold: float) -> pd.Series:
    proba = backend.predict_proba_up(df)
    return (proba > threshold).astype(int)
```

### Pattern 2: Broker Protocol with Fake Double (Hexagonal / Ports & Adapters, Lite)

**What:** `Broker` is a Protocol; `AlpacaPaperBroker` is the production adapter; `FakeBroker` is an in-memory adapter used in tests. `bot.py` depends on `Broker`, never on `alpaca.trading.client` directly.

**When to use:** Any external I/O you want to unit-test without mocking the SDK.

**Trade-offs:**
- Pro: `bot.py` logic is fully unit-testable without network, without `unittest.mock.patch`
- Pro: `FakeBroker` can enforce invariants (e.g. reject sells with no position) and double as a sanity check
- Con: one extra layer; for a solo project of this size, that layer is cheap

**Example:**

```python
# stock_ai/execution/broker.py
from typing import Protocol
from stock_ai.execution.orders import Order, Position, Account

class Broker(Protocol):
    def get_account(self) -> Account: ...
    def get_positions(self) -> list[Position]: ...
    def submit_order(self, order: Order) -> str: ...  # returns broker order id
```

```python
# stock_ai/execution/orders.py
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class Order:
    ticker: str
    side: Literal["buy", "sell"]
    qty: int
    order_type: Literal["market"] = "market"
    time_in_force: Literal["day"] = "day"
```

```python
# stock_ai/execution/paper.py
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

class AlpacaPaperBroker:
    def __init__(self, api_key: str, secret_key: str):
        self._client = TradingClient(api_key, secret_key, paper=True)

    def submit_order(self, order: Order) -> str:
        req = MarketOrderRequest(
            symbol=order.ticker,
            qty=order.qty,
            side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        resp = self._client.submit_order(req)
        return str(resp.id)
    # get_account, get_positions similarly
```

```python
# stock_ai/execution/fake.py
class FakeBroker:
    def __init__(self, starting_cash: float = 100_000):
        self.submitted: list[Order] = []
        self._cash = starting_cash
        self._positions: dict[str, int] = {}

    def submit_order(self, order: Order) -> str:
        self.submitted.append(order)
        delta = order.qty if order.side == "buy" else -order.qty
        self._positions[order.ticker] = self._positions.get(order.ticker, 0) + delta
        return f"fake-{len(self.submitted)}"
    # ...
```

### Pattern 3: Thin Entry Point / Pure Library (preserves existing idiom)

**What:** `app.py` and `bot.py` only do: (1) read config, (2) call `stock_ai.*` functions, (3) render/log. They contain **no business logic** — same way `main.py` just dispatches.

**When to use:** Every entry point in this project. Keeps the testable surface inside `stock_ai/`.

**Trade-offs:**
- Pro: Streamlit app and CLI and bot share one logic path; a backtest in the UI is bit-for-bit the same backtest the CLI runs
- Con: Requires discipline — temptation to put a one-off calculation inline in `app.py` must be resisted; refactor it into `stock_ai/`

**Example (`bot.py` skeleton):**

```python
# bot.py
from stock_ai.config.settings import load_settings
from stock_ai.data.loader import fetch_price_history
from stock_ai.features.indicators import add_features
from stock_ai.models.rf_backend import RandomForestBackend
from stock_ai.models.jev_backend import JevBackend
from stock_ai.strategy.ranker import top_n
from stock_ai.execution.paper import AlpacaPaperBroker
from stock_ai.execution.orders import Order
from stock_ai.universe.tickers import DEFAULT_UNIVERSE

def run_eod(backend_name: str = "random_forest", top: int = 5, max_notional_per_name: float = 1000):
    s = load_settings()
    broker = AlpacaPaperBroker(s.alpaca_key, s.alpaca_secret)
    backend = RandomForestBackend() if backend_name == "random_forest" else JevBackend(api_key=s.jev_key)

    scored = {}
    for ticker in DEFAULT_UNIVERSE:
        df = add_features(fetch_price_history(ticker, s.train_start, s.today))
        backend.fit(df.iloc[:-1])  # train on everything except latest row
        proba = backend.predict_proba_up(df.tail(1)).iloc[0]
        scored[ticker] = proba

    chosen = top_n(scored, n=top)
    for ticker in chosen:
        price = fetch_price_history(ticker, s.today, None).iloc[-1]["Close"]
        qty = int(max_notional_per_name // price)
        if qty > 0:
            broker.submit_order(Order(ticker=ticker, side="buy", qty=qty))

if __name__ == "__main__":
    run_eod()
```

The `run_eod` function takes a `broker: Broker | None = None` kwarg in practice so tests can inject `FakeBroker`.

### Pattern 4: Multi-Ticker as Composition, Not Replacement

**What:** Single-ticker backtest (`run_backtest`) stays unchanged. `multi_engine.run_portfolio_backtest(tickers, backend, ...)` loops over tickers, scores each daily, uses `ranker.top_n` to pick holdings, aggregates per-ticker return series into a portfolio curve.

**When to use:** Any time the single-ticker API is already honest and useful; wrap it, don't rewrite it.

**Trade-offs:**
- Pro: CLI `python main.py backtest --ticker AAPL` keeps working unchanged
- Pro: Multi-ticker is one small new file, not a refactor
- Con: Simple vectorization is left on the table (fine at 50 tickers; revisit at 500+)

## Data Flow

### Backtest Explorer Flow (Streamlit)

```
User fills form in browser
     │
     ▼
app.py                       ← widgets: ticker list, dates, cost, threshold, backend
     │
     ├─ load_settings()      ← reads .env (optional for backtest)
     │
     ├─ For each ticker:
     │    fetch_price_history → add_features
     │
     ├─ backend = RandomForestBackend() OR JevBackend(...)
     │
     ├─ run_portfolio_backtest(tickers, backend, cost_bps, threshold, top_n)
     │       │
     │       ├─ for each ticker: fit → predict_proba_up → generate_signals → run_backtest
     │       └─ ranker.top_n applied cross-sectionally per day
     │
     ├─ metrics dict → st.metric widgets
     └─ cumulative return series + buy/sell markers → ui.charts.price_with_signals → st.plotly_chart
```

**Streamlit import rule:** `app.py` imports FROM `stock_ai.*` and `ui.*`. **Nothing in `stock_ai/` or `ui/` imports `streamlit`.** `ui/charts.py` returns Plotly `Figure` objects; `app.py` is the only module that calls `st.plotly_chart`, `st.form`, etc. This keeps `stock_ai` runnable headless (CLI, bot, tests) and makes the UI replaceable.

**Caching:** Use `@st.cache_data` on wrapper functions **inside `app.py`** that call `fetch_price_history`. Do not put `@st.cache_data` inside `stock_ai/` — that would couple the library to Streamlit.

### Paper-Trading Loop Flow (bot.py, run daily at EOD)

```
cron / manual kickoff
     │
     ▼
bot.run_eod(backend_name, top_n, risk_caps)
     │
     ├─ load_settings()                     ← API keys from .env
     ├─ broker = AlpacaPaperBroker(...)      ← or FakeBroker in tests
     ├─ backend = <chosen SignalBackend>
     │
     ├─ For each ticker in universe:
     │     fetch_price_history → add_features → backend.fit(history) → backend.predict_proba_up(latest row)
     │
     ├─ scored: dict[ticker, float]
     ├─ chosen = ranker.top_n(scored, n=top)
     │
     ├─ positions_current = broker.get_positions()
     ├─ orders = diff(positions_current, chosen, max_notional_per_name)
     │                                          ← pure function in execution/orders.py
     │
     ├─ For each order: broker.submit_order(order)
     └─ log each submission (ticker, side, qty, proba, reason)
```

Key testability points:
- `diff()` is pure — takes current positions + target tickers + caps, returns `list[Order]`. Unit-testable with no broker.
- `run_eod(broker=FakeBroker())` runs the entire loop deterministically in a test; assert on `broker.submitted`.

### State Management

**No persistent state in v1** — matches existing architecture. Each `app.py` form submission re-fetches and retrains. Each `bot.py` run re-fetches and retrains. Model persistence is explicitly deferred to v2 (`PROJECT.md` §Deferred).

Streamlit `@st.cache_data` on the data fetch provides within-session caching (per unique `(ticker, start, end)` key) which is enough to make the UI feel responsive without introducing a disk cache.

### Key Data Flows

1. **Historical fetch:** `yfinance → pandas.DataFrame` (unchanged from current pipeline)
2. **Scoring:** `DataFrame → SignalBackend.predict_proba_up → Series[float]` (replaces direct `model.predict_proba` call)
3. **Ranking:** `dict[ticker, float] → list[ticker]` via `ranker.top_n` (new)
4. **Execution:** `list[ticker] + current positions → list[Order] → Broker.submit_order → broker order ids` (new)

## Suggested Build Order (and dependency chain)

The milestone decomposes cleanly into phases that each ship something runnable:

**Phase A: Signal Backend Abstraction (blocks everything else)**
- Add `stock_ai/models/base.py` (`SignalBackend` Protocol)
- Add `stock_ai/models/rf_backend.py` wrapping existing `classifier.py`
- Refactor `generate_signals()` to accept a `SignalBackend` instead of a raw `RandomForestClassifier`
- Update `main.py` to construct `RandomForestBackend()` and pass it through
- All existing tests must still pass; add `test_rf_backend.py`

**Phase B: Config + Universe (small, independent)**
- Add `stock_ai/config/settings.py` with `python-dotenv` loader
- Add `stock_ai/universe/tickers.py` with default list
- `.env.example` populated

**Phase C: Streamlit Explorer on single-ticker (visible win fast)**
- Add `app.py` + `ui/charts.py`
- Form inputs → run_backtest on one ticker → render metrics + Plotly chart
- Uses only Phase A artifacts

**Phase D: Multi-ticker Ranking (depends on A + B)**
- Add `stock_ai/strategy/ranker.py` (pure function)
- Add `stock_ai/backtest/multi_engine.py` (loops `engine.run_backtest` + applies ranker)
- Extend `app.py` form to accept comma-separated tickers + top-N
- Does NOT touch `main.py` (single-ticker CLI stays stable)

**Phase E: Broker Abstraction (depends on B)**
- Add `stock_ai/execution/{broker,orders,fake}.py`
- Pure `diff(positions, targets, caps)` helper + unit tests with `FakeBroker`
- No Alpaca dependency yet — ships as a thoroughly tested skeleton

**Phase F: Alpaca Adapter (depends on E)**
- Add `stock_ai/execution/paper.py` using `alpaca-py`
- Smoke-test against paper account (manual, documented)

**Phase G: EOD Bot Loop (depends on A + D + F)**
- Add `bot.py`
- `run_eod(backend, broker=None, ...)` taking injected broker
- Tests use `FakeBroker` + fixed DataFrames so no network needed
- Add Streamlit page: "Place paper orders for today" (calls `run_eod` with real `AlpacaPaperBroker`)

**Phase H: Jev Backend (depends on A, parallel-able with D–G)**
- Add `stock_ai/models/jev_backend.py` conforming to `SignalBackend`
- Add Streamlit backend-selector dropdown (RF vs Jev)
- Add side-by-side comparison view in the explorer

**Why this order:**
- A is a true blocker — once the Protocol exists everything downstream is clean. Doing it first prevents a mid-project refactor.
- Jev (H) is last because it is the riskiest unknown (`PROJECT.md` risk #1). All earlier phases ship real value even if Jev never materializes.
- The broker loop (E–G) is split so unit-testable logic lands before the SDK dependency, matching the existing testing culture.

## Testability Guidance

| Concern | Approach |
|---------|----------|
| Streamlit app logic | Keep `app.py` thin. Business logic lives in `stock_ai/`. Test library, not the UI. Chart builders in `ui/charts.py` return Plotly figures that can be snapshot-tested via `figure.to_dict()` equality on key fields. |
| Alpaca client | Never call `alpaca-py` from `bot.py`. Depend on `Broker` Protocol; inject `FakeBroker` in `test_bot_loop.py`. The only test that actually touches Alpaca is a manually-run smoke script, not part of pytest default. |
| Jev client | Same pattern: `JevBackend` wraps the SDK; tests use a recorded fixture (JSON response) + mocked HTTP via `httpx.MockTransport` or `responses`. Do not mock `JevBackend` itself — mock at the HTTP boundary. |
| Order diffing | `execution/orders.diff(current_positions, target_tickers, caps) → list[Order]` is pure; test exhaustively (empty→full, full→empty, partial rotation, caps enforcement). |
| Multi-ticker backtest | `multi_engine` composed from `engine` + `ranker`; test aggregation with a fixture of 3 synthetic tickers. |
| Backward compat | `tests/test_signal.py` and `tests/test_backtest.py` continue to pass unchanged. If a Phase A refactor breaks them, the Protocol wrapper is wrong. |

## Anti-Patterns

### Anti-Pattern 1: Letting Streamlit creep into `stock_ai/`

**What people do:** Sprinkle `@st.cache_data` decorators or `st.error(...)` calls inside library modules.
**Why it's wrong:** The library stops being importable from `bot.py` or pytest without Streamlit's runtime context. Breaks CLI, breaks tests, couples the pipeline to a UI framework.
**Do this instead:** All `st.*` lives in `app.py`. If caching matters inside the library, use `functools.lru_cache` or a plain dict keyed by `(ticker, start, end)`.

### Anti-Pattern 2: Mocking `alpaca.trading.client.TradingClient` in bot tests

**What people do:** `@patch("alpaca.trading.client.TradingClient")` in every test, assert against call args.
**Why it's wrong:** Couples tests to the SDK's internal shape. SDK upgrade breaks dozens of unrelated tests. Encourages testing that "mock was called" instead of behavior.
**Do this instead:** Depend on `Broker` Protocol in production code; inject `FakeBroker()` in tests. Assert on `broker.submitted` — behavior, not call shape.

### Anti-Pattern 3: Jev as a special case in `generate_signals`

**What people do:** `if backend == "jev": call_jev_api(...) else: model.predict_proba(...)`.
**Why it's wrong:** Every new backend requires editing core strategy code. Violates open-closed. The whole point of the Protocol is lost.
**Do this instead:** `generate_signals(backend: SignalBackend, df, threshold)` — no branching, backend is a parameter.

### Anti-Pattern 4: Rebuilding the single-ticker pipeline for multi-ticker

**What people do:** Write a brand new `multi_backtest.py` that re-implements feature engineering, signal generation, and PnL inline.
**Why it's wrong:** Doubles the testing surface, drifts from the single-ticker version, breaks the "one function per pipeline stage" convention.
**Do this instead:** `multi_engine.run_portfolio_backtest` loops over tickers calling the existing `run_backtest` per leg and aggregates. One new file, ~30 lines.

### Anti-Pattern 5: Reading `os.environ` scattered across modules

**What people do:** `os.getenv("ALPACA_API_KEY")` directly in `paper.py`, `jev_backend.py`, etc.
**Why it's wrong:** Config becomes implicit; tests can't override cleanly; secrets handling is spread out.
**Do this instead:** `stock_ai/config/settings.py` is the single `.env` reader. Entry points call `load_settings()` once and pass the resulting `Settings` object (or specific fields) into constructors.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| yfinance | Unchanged — `data/loader.py` wraps `yfinance.download` | No SLA; `PROJECT.md` risk #4 flags Alpaca market data as fallback. Keep the function signature stable so swapping is a one-file change. |
| Alpaca Paper (`alpaca-py`) | Wrapped by `AlpacaPaperBroker` behind `Broker` Protocol | Paper endpoint `paper=True`. Rate limit 200 req/min free tier. Market orders only in v1. |
| Jev | Wrapped by `JevBackend` behind `SignalBackend` Protocol | Treat as unproven (`PROJECT.md` risk #1). Mock at HTTP boundary in tests. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `app.py` ↔ `stock_ai` | Direct function calls | One-way. `stock_ai` never imports Streamlit. |
| `bot.py` ↔ `stock_ai` | Direct function calls + `Broker` Protocol injection | One-way. `stock_ai/execution/paper.py` is the only file importing `alpaca`. |
| `signal.py` ↔ model | `SignalBackend` Protocol | Replaces direct `RandomForestClassifier` dependency. |
| `strategy/signal.py` ↔ `strategy/ranker.py` | Both consumed by `multi_engine.py`; no direct import between them | Keeps single-ticker and cross-sectional orthogonal. |
| `main.py` ↔ new code | `main.py` constructs `RandomForestBackend()` and threads it through — otherwise unchanged | Preserves CLI backward compat. |

## Sources

- Existing project files: `.planning/codebase/ARCHITECTURE.md`, `STRUCTURE.md`, `CONVENTIONS.md`, `.planning/PROJECT.md` — HIGH confidence (direct reads)
- Streamlit layout convention (`app.py` at project root, `streamlit run app.py`) — Streamlit official docs, HIGH confidence
- Alpaca-py `TradingClient(paper=True)` pattern — alpaca-py README/docs, HIGH confidence
- Protocol / structural subtyping (PEP 544) — Python docs, HIGH confidence
- Hexagonal / Ports-and-Adapters-lite pattern for broker abstraction — community pattern (Cosmic Python, "Architecture Patterns with Python"), MEDIUM confidence as applied here but widely used

---
*Architecture research for: EOD paper-trading bot + Streamlit explorer extending a linear pandas pipeline*
*Researched: 2026-10-06*

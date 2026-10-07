# Stock-AI — Requirements (v1 Milestone)

**Milestone:** v1 — Jev-powered paper-trading bot you can show mentors
**Source:** `.planning/PROJECT.md` Active list, refined by `.planning/research/*`
**Last updated:** 2026-10-07
**Mode:** Vertical MVP (each phase ships an end-to-end slice)

Every requirement is a hypothesis until shipped and validated. Checked boxes get moved to `PROJECT.md`'s Validated section at phase-end.

---

## v1 Requirements

### Signal Backend (SB)

Pre-work shared by every downstream slice. From `research/ARCHITECTURE.md` Phase A — called out as the single load-bearing dependency.

- [ ] **SB-01**: `SignalBackend` Protocol defined in `stock_ai/models/base.py` with `fit(X, y)` and `predict_proba_up(X)` methods
- [ ] **SB-02**: Existing RandomForest wrapped as `RandomForestBackend` conforming to `SignalBackend`
- [ ] **SB-03**: `generate_signals(backend, df, threshold)` refactored to accept a `SignalBackend` instance (no `if/else` on backend type)
- [ ] **SB-04**: Existing single-ticker CLI (`python main.py backtest --ticker AAPL`) output remains byte-identical after refactor (regression test)

### Configuration & Universe (CU)

From `research/STACK.md` + `research/PITFALLS.md` #9. Dotenv-only secrets; universe is config, not hardcoded.

- [ ] **CU-01**: `python-dotenv` wired up — `load_dotenv()` called from a single entry point so `.env` is read once per run
- [ ] **CU-02**: `stock_ai/config.py` module with typed `Settings` class exposing `anthropic_api_key`, `alpaca_api_key`, `alpaca_secret_key`, `typesafe_api_key` (all optional at this stage)
- [ ] **CU-03**: `Settings.__repr__` redacts all secret values (never prints key material in tracebacks)
- [ ] **CU-04**: Default universe of 20–50 large-cap US liquid tickers defined in `stock_ai/config/universe.py` (editable without code changes)
- [ ] **CU-05**: `.env.example` updated with every required/optional key documented

### Streamlit Backtest Explorer (UI)

From `PROJECT.md` v1 scope + `research/FEATURES.md` table-stakes + `research/PITFALLS.md` #6, #10.

- [ ] **UI-01**: `app.py` at project root launches via `streamlit run app.py` on `localhost:8501`
- [ ] **UI-02**: Inputs: ticker (single or multi), date range, cost (bps), confidence threshold, model backend selector (RandomForest / Jev)
- [ ] **UI-03**: Inputs wrapped in `st.form` so backtest only runs on explicit submit (no rerun thrash on slider moves)
- [ ] **UI-04**: `@st.cache_data` on price-history fetch; `@st.cache_resource` on trained models
- [ ] **UI-05**: Results view shows: test accuracy, OOS return, buy-and-hold return, Sharpe, trade count, max drawdown
- [ ] **UI-06**: In-sample vs out-of-sample results clearly separated (same honesty as current CLI)
- [ ] **UI-07**: Interactive price chart (Plotly) with buy/sell markers on the test slice
- [ ] **UI-08**: `showErrorDetails = false` in Streamlit config to prevent secret leakage in tracebacks

### Multi-Ticker Cross-Sectional Strategy (MT)

From `PROJECT.md` v1 scope + `research/ARCHITECTURE.md` Phase D + `research/PITFALLS.md` #3, #4, #5.

- [ ] **MT-01**: `stock_ai/backtest/multi_engine.py` runs per-ticker legs then combines into a portfolio return series (NOT averaging per-ticker Sharpes)
- [ ] **MT-02**: `stock_ai/strategy/ranker.py` provides `top_n(predictions, n)` for cross-sectional top-N selection
- [ ] **MT-03**: Canonical NYSE trading-calendar reindex applied before any multi-ticker alignment (prevents silent lookahead from mismatched indices)
- [ ] **MT-04**: Portfolio-level Sharpe computed on the combined daily return series, not averaged across tickers
- [ ] **MT-05**: Single-ticker CLI from Phase SB continues to work unchanged
- [ ] **MT-06**: Default universe size + date range chosen so survivorship bias is bounded (short windows, documented limitation)

### Broker Abstraction (BR)

From `research/ARCHITECTURE.md` Phase E — ports-and-adapters pattern so bot stays testable without hitting Alpaca.

- [ ] **BR-01**: `Broker` Protocol defined in `stock_ai/execution/base.py` (methods: `get_account`, `get_positions`, `submit_order`, `cancel_order`)
- [ ] **BR-02**: `FakeBroker` implementation for tests — deterministic, in-memory
- [ ] **BR-03**: Order-diff logic (given current positions + target positions, produce orders) is pure and unit-testable with `FakeBroker`
- [ ] **BR-04**: `DRY_RUN` env flag short-circuits `submit_order` to log-only mode

### Alpaca Paper Trading (AP)

From `PROJECT.md` v1 scope + `research/ARCHITECTURE.md` Phase F + `research/PITFALLS.md` #1, #2, #7.

- [ ] **AP-01**: `stock_ai/execution/paper.py` is the sole module importing `alpaca-py`
- [ ] **AP-02**: `AlpacaPaperBroker` conforms to `Broker` Protocol
- [ ] **AP-03**: `TradingClient(..., paper=True)` on construction; base-URL assertion that `paper-api` is in the URL (prevents live-endpoint accidents)
- [ ] **AP-04**: Idempotent order submission — `client_order_id = f"{eastern_date}_{ticker}_{side}"` so Streamlit reruns can't double-submit
- [ ] **AP-05**: All timezones handled via `zoneinfo.ZoneInfo("America/New_York")` — no naive `datetime.today()`
- [ ] **AP-06**: Pre-flight `get_asset(ticker)` checks tradability and fractional-share eligibility before submitting

### EOD Bot Loop (BL)

From `research/ARCHITECTURE.md` Phase G + `research/PITFALLS.md` #8.

- [ ] **BL-01**: `bot.py` at project root exposes `run_eod(broker)` for scheduled or manual invocation
- [ ] **BL-02**: Hard cap on per-order $ amount (configurable, default $500 on paper)
- [ ] **BL-03**: Hard cap on daily order count (configurable, default 20)
- [ ] **BL-04**: `KILL_SWITCH` file at repo root halts order submission on sight
- [ ] **BL-05**: Default `DRY_RUN=true` — must be explicitly set `false` in `.env` to place paper orders
- [ ] **BL-06**: Two-step UI flow: "Preview orders" → "Confirm & submit"
- [ ] **BL-07**: `pytest-socket` test proves `import bot` makes zero network calls

### Jev Signal Backend (JV)

From `PROJECT.md` v1 scope + `research/STACK.md` + `research/PITFALLS.md` #11-14. Last phase on purpose per PROJECT.md Risk #1.

- [ ] **JV-01**: `JevBackend` in `stock_ai/models/jev_backend.py` conforms to `SignalBackend` Protocol
- [ ] **JV-02**: `typesafe-sdk` pinned to exact minor version (`typesafe-sdk==1.3.*`); model alias pinned (not `jev-latest`)
- [ ] **JV-03**: `JevBackend` returns `pd.Series[float]` of up-probabilities — no `Choice` or SDK type leakage to downstream code
- [ ] **JV-04**: HTTP calls mockable for tests (`pytest-httpx` or equivalent); no live Jev calls in test suite
- [ ] **JV-05**: Backtest explorer shows RandomForest vs Jev side-by-side on the same universe/period
- [ ] **JV-06**: Jev used for live signal scoring only; backtests over long history continue using RandomForest to avoid cost spikes

### Reliability & Honesty (RH)

From `PROJECT.md` v1 scope + `research/PITFALLS.md` §Verification "mentor-demo safety floor".

- [ ] **RH-01**: `pytest tests/` passes with ≥10 new tests covering the pitfall anti-regressions (list below)
- [ ] **RH-02**: README updated with CLI + Streamlit usage, prerequisites, and `.env` setup instructions
- [ ] **RH-03**: `.env.example` is the single source of truth for required env vars; no `.streamlit/secrets.toml`
- [ ] **RH-04**: `.gitignore` audit confirms `.env` and `KILL_SWITCH` won't accidentally be committed

**Required anti-regression test coverage** (per `research/PITFALLS.md`):

1. `test_paper_endpoint_assertion` — Alpaca construction refuses non-paper URL
2. `test_idempotent_submission` — Same `client_order_id` deduped
3. `test_portfolio_sharpe_math` — Equal-weight 2-ticker portfolio Sharpe is NOT the mean of per-ticker Sharpes
4. `test_portfolio_sharpe_not_average_of_per_ticker` — Explicit anti-regression against the inflation-by-sqrt(N) bug
5. `test_trading_day_timezone` — `today_trading_date()` uses Eastern time
6. `test_jev_backend_mocked_http` — `JevBackend.predict_proba_up` works with mocked HTTP
7. `test_bot_import_no_network` — `import bot` makes no network calls
8. `test_settings_repr_redacted` — `repr(Settings(...))` contains no secret values
9. `test_order_cap_enforced` — Order with `qty * price > cap` is rejected before submission
10. `test_dry_run_short_circuit` — `DRY_RUN=true` returns logged order without hitting broker

---

## v2 Requirements (Deferred)

Captured for traceability but **not in v1 scope**. Will move to Active in a future milestone.

- Walk-forward backtesting with rolling retrain
- Bootstrap confidence intervals on Sharpe
- Model persistence (joblib dump/load)
- News/filings sentiment via FinGPT or similar
- Volatility-targeted position sizing
- Max portfolio drawdown halt
- Point-in-time universe membership (true survivorship-bias fix)
- Per-ticker transaction cost modeling (vs flat bps)
- CI pipeline (GitHub Actions)
- Multi-user auth / cloud deployment

---

## Out of Scope

Captured from `PROJECT.md`. Not v1, not v2 — explicit exclusions.

- Live trading with real money
- Intraday trading / sub-daily bars
- Options, futures, crypto, FX
- Shorting, leverage, margin strategies
- High-frequency / market-making
- Mobile apps
- SaaS / multi-tenant

---

## Traceability

Phase mapping is derived from `research/ARCHITECTURE.md` 8-phase build order and will be finalized in `ROADMAP.md`:

| Phase | REQ-IDs covered |
|---|---|
| Phase A — SignalBackend Protocol | SB-01, SB-02, SB-03, SB-04 |
| Phase B — Config & Universe | CU-01, CU-02, CU-03, CU-04, CU-05 |
| Phase C — Streamlit single-ticker explorer | UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08 |
| Phase D — Multi-ticker cross-sectional | MT-01, MT-02, MT-03, MT-04, MT-05, MT-06 |
| Phase E — Broker Protocol + FakeBroker | BR-01, BR-02, BR-03, BR-04 |
| Phase F — Alpaca paper adapter | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06 |
| Phase G — EOD bot loop | BL-01, BL-02, BL-03, BL-04, BL-05, BL-06, BL-07 |
| Phase H — Jev backend adapter | JV-01, JV-02, JV-03, JV-04, JV-05, JV-06 |
| Cross-phase | RH-01, RH-02, RH-03, RH-04 (verified at milestone close) |

Open design questions flagged in `research/PITFALLS.md` to be resolved during their respective phase planning:
- TimeInForce policy (OPG vs CLS vs DAY) — Phase F
- Pooled vs per-ticker model architecture — Phase D
- Jev pricing / model alias confirmation — Phase H

---

*Milestone: v1 — paper-trading bot. Generated: 2026-10-07.*

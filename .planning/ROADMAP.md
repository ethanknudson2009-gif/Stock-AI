# Stock-AI — Roadmap (v1 Milestone)

**Milestone:** v1 — Jev-powered paper-trading bot you can show mentors
**Timeline target:** 2–4 weeks
**Granularity:** coarse
**Mode:** Vertical MVP (each phase ships an end-to-end slice runnable at HEAD)
**Coverage:** 42/42 v1 REQ-IDs mapped
**Last updated:** 2026-10-07

Phase order follows `research/ARCHITECTURE.md` 8-phase build order. **Phase A is load-bearing** — nothing downstream starts before A ships. Phase H (Jev) is parallelizable with D–G once A ships. Phases B/C/D/E/F/G otherwise follow the natural dependency chain.

---

## Phases

- [ ] **Phase A: SignalBackend Protocol** — load-bearing refactor that unblocks every other phase
- [ ] **Phase B: Config & Universe** — dotenv secrets + default large-cap universe
- [ ] **Phase C: Streamlit Single-Ticker Explorer** — browser UI reproducing the CLI backtest
- [ ] **Phase D: Multi-Ticker Cross-Sectional Strategy** — portfolio-level ranking + honest Sharpe
- [ ] **Phase E: Broker Protocol + FakeBroker** — testable execution layer, no SDK yet
- [ ] **Phase F: Alpaca Paper Adapter** — real paper broker behind the Protocol
- [ ] **Phase G: EOD Bot Loop** — `bot.py` wires everything into a daily paper-trade loop
- [ ] **Phase H: Jev Signal Backend** — second `SignalBackend` + RF-vs-Jev comparison in UI

---

## Phase Details

### Phase A: SignalBackend Protocol
**Goal:** Introduce the `SignalBackend` Protocol and wrap existing RandomForest behind it without changing CLI behavior, so every downstream phase can depend on a stable abstraction.
**Mode:** mvp
**Depends on:** Nothing (first phase)
**Parallel with:** Nothing — A is explicitly load-bearing per `research/ARCHITECTURE.md` §Suggested Build Order
**Requirements:** SB-01, SB-02, SB-03, SB-04
**Success Criteria** (what must be TRUE):
  1. `python main.py backtest --ticker AAPL` prints the same metrics (accuracy, OOS return, Sharpe, trade count) as before the refactor, byte-identical where possible
  2. `generate_signals()` accepts any object conforming to `SignalBackend` with no `isinstance` branching
  3. A new `test_rf_backend.py` passes and all 6 pre-existing pytest tests still pass green
  4. `grep -r "RandomForestClassifier" stock_ai/strategy/ stock_ai/backtest/` returns zero hits (no leakage of concrete model type outside `rf_backend.py`)
**Plans:** 1 plan
Plans:
- [ ] A-01-PLAN.md — Define SignalBackend Protocol, wrap RandomForest behind it, refactor generate_signals, prove byte-identical CLI output
**Risks (HIGH-severity pitfalls to mitigate this phase):**
  - *(Phase A has no HIGH pitfalls — the risk is backward-compat regression; mitigated by SB-04)*
**Test coverage delivered (from RH-01 safety floor):** none directly, but the Protocol enables tests #6 and #10 downstream

### Phase B: Config & Universe
**Goal:** Centralize `.env` loading, redact secrets, and define a default large-cap universe that is config, not code.
**Mode:** mvp
**Depends on:** Phase A (`SignalBackend` imports consistency)
**Parallel with:** Nothing (small enough to just ship)
**Requirements:** CU-01, CU-02, CU-03, CU-04, CU-05
**Success Criteria** (what must be TRUE):
  1. `from stock_ai.config import Settings; print(repr(Settings(...)))` prints redacted key values — never the raw secret
  2. `load_dotenv()` is called from exactly one place per entry point (`main.py`, future `app.py`, future `bot.py`) — not sprinkled across modules
  3. `stock_ai/universe/tickers.py` exposes a `DEFAULT_UNIVERSE` list of 20–50 large-cap tickers editable without touching any other file
  4. `.env.example` lists every optional key with a comment explaining what each unlocks
**Plans:** TBD
**Risks (HIGH-severity pitfalls to mitigate this phase):**
  - Pitfall #4 (Survivorship bias) — universe docstring must disclose that it is a current snapshot, not point-in-time membership
  - Pitfall #9 (`st.secrets` vs `.env` double-source) — `.env` only, no `.streamlit/secrets.toml`
**Test coverage delivered (from RH-01 safety floor):** #8 `test_settings_repr_redacted`

### Phase C: Streamlit Single-Ticker Explorer
**Goal:** User can `streamlit run app.py` and reproduce the single-ticker CLI backtest in a browser with form inputs, honest metrics, and a Plotly chart.
**Mode:** mvp
**Depends on:** Phase A (uses `RandomForestBackend`), Phase B (`.env` + redacted settings)
**Parallel with:** Nothing before D
**UI hint:** yes
**Requirements:** UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08
**Success Criteria** (what must be TRUE):
  1. `streamlit run app.py` opens `localhost:8501` with form inputs for ticker, date range, cost (bps), threshold, and backend selector
  2. Submitting the form shows OOS return, buy-and-hold return, Sharpe, trade count, max drawdown, test accuracy — in-sample and out-of-sample clearly separated
  3. Moving a slider or editing an input does NOT re-fetch data or re-train the model until the user clicks "Run Backtest" (form gating works)
  4. A Plotly price chart renders with buy/sell markers from the test slice
  5. Triggering an exception (bad ticker, empty range) surfaces a redacted `st.error` — the Streamlit traceback does not leak API keys
**Plans:** TBD
**Risks (HIGH-severity pitfalls to mitigate this phase):**
  - Pitfall #6 (Rerun thrash) — `st.form` + `@st.cache_data` + `@st.cache_resource` are non-negotiable
  - Pitfall #9 (`st.secrets` vs `.env`) — reinforced; only `load_dotenv()` in `app.py`
  - Pitfall #10 (Traceback leaks) — `showErrorDetails = false` + redacting error wrapper
**Test coverage delivered (from RH-01 safety floor):** none directly — Streamlit itself is not unit-tested; underlying library tests cover logic

### Phase D: Multi-Ticker Cross-Sectional Strategy
**Goal:** User can run a top-N cross-sectional backtest over a 20–50 ticker universe with portfolio-level Sharpe (not averaged per-ticker) and canonical trading-day alignment.
**Mode:** mvp
**Depends on:** Phase A (SignalBackend), Phase B (universe), Phase C (UI to render results)
**Parallel with:** Phase H can begin in parallel once A ships
**UI hint:** yes
**Requirements:** MT-01, MT-02, MT-03, MT-04, MT-05, MT-06
**Success Criteria** (what must be TRUE):
  1. User enters a comma-separated ticker list (or picks "Default Universe") and a top-N value, hits Run, and sees a portfolio equity curve plus portfolio Sharpe
  2. Reported Sharpe on a randomized signal across 20+ tickers hovers around 0 (±a few tenths) — proving the math is NOT the average-of-per-ticker-Sharpes bug
  3. Portfolio return series has zero unexplained NaN days — every ticker is reindexed to a canonical NYSE trading calendar before aggregation
  4. The single-ticker CLI (`python main.py backtest --ticker AAPL`) still produces identical output to Phase A's checkpoint
  5. UI labels portfolio Sharpe explicitly as "Portfolio Sharpe (equal-weight top-N, daily rebalance)" — never bare "Sharpe"
**Plans:** TBD
**Risks (HIGH-severity pitfalls to mitigate this phase):**
  - Pitfall #3 (Average-of-Sharpes) — true portfolio-return series required; anti-regression test mandatory
  - Pitfall #4 (Survivorship bias) — short-window default + README/UI disclosure
  - Pitfall #5 (Date alignment) — canonical NYSE calendar reindex
**Test coverage delivered (from RH-01 safety floor):** #3 `test_portfolio_sharpe_math`, #4 `test_portfolio_sharpe_not_average_of_per_ticker`

### Phase E: Broker Protocol + FakeBroker
**Goal:** A `Broker` Protocol and `FakeBroker` test double ship with a pure order-diff function, so bot logic becomes fully unit-testable before any SDK is pulled in.
**Mode:** mvp
**Depends on:** Phase B (settings module)
**Parallel with:** Phase H
**Requirements:** BR-01, BR-02, BR-03, BR-04
**Success Criteria** (what must be TRUE):
  1. `FakeBroker().submit_order(...)` is deterministic, in-memory, and records every submission for test assertion
  2. `diff(current_positions, target_tickers, caps)` is a pure function with unit tests covering empty→full, full→empty, partial rotation, and cap enforcement
  3. Setting `DRY_RUN=true` causes `submit_order` to return a logged no-op without any side effect that would reach a real broker
  4. The `Broker` Protocol has no `alpaca-py` import anywhere in `stock_ai/execution/` except (future) `paper.py`
**Plans:** TBD
**Risks (HIGH-severity pitfalls to mitigate this phase):**
  - Pitfall #2 (Idempotency) — `FakeBroker` enforces that duplicate `client_order_id` produces a single submission; test lands here
**Test coverage delivered (from RH-01 safety floor):** #9 `test_order_cap_enforced`, #10 `test_dry_run_short_circuit`

### Phase F: Alpaca Paper Adapter
**Goal:** `AlpacaPaperBroker` conforms to the `Broker` Protocol, provably hits the paper endpoint only, and submits idempotent orders with Eastern-time trading-day semantics.
**Mode:** mvp
**Depends on:** Phase E (Broker Protocol)
**Parallel with:** Phase H
**Requirements:** AP-01, AP-02, AP-03, AP-04, AP-05, AP-06
**Success Criteria** (what must be TRUE):
  1. Constructing `AlpacaPaperBroker` asserts `paper-api.alpaca.markets` is in the client base URL — construction fails loudly if ever otherwise
  2. Submitting the same logical order twice (same date, ticker, side) produces exactly one filled order on the paper account (idempotency via `client_order_id`)
  3. `trading_day_today()` returns the correct Eastern-time trading date even when the system clock is in PT at 11:59pm local
  4. Pre-flight `get_asset()` check rejects non-tradable tickers before any `submit_order` call reaches Alpaca
  5. `stock_ai/execution/paper.py` is the ONLY module in the repo that imports from `alpaca-py`
**Plans:** TBD
**Risks (HIGH-severity pitfalls to mitigate this phase):**
  - Pitfall #1 (Live endpoint) — hard assertion in `__init__`
  - Pitfall #2 (Non-idempotent submission) — deterministic `client_order_id`
  - Pitfall #7 (Timezone confusion) — `zoneinfo.ZoneInfo("America/New_York")` everywhere
**Test coverage delivered (from RH-01 safety floor):** #1 `test_paper_endpoint_assertion`, #2 `test_idempotent_submission`, #5 `test_trading_day_timezone`

### Phase G: EOD Bot Loop
**Goal:** `bot.py` runs an end-to-end paper-trade loop with hard caps, a kill-switch file, DRY_RUN default, and a two-step preview-confirm UI integration — importable without any network activity.
**Mode:** mvp
**Depends on:** Phase A (SignalBackend), Phase D (multi-ticker ranking), Phase F (AlpacaPaperBroker)
**Parallel with:** Phase H (both can land independently after F)
**UI hint:** yes
**Requirements:** BL-01, BL-02, BL-03, BL-04, BL-05, BL-06, BL-07
**Success Criteria** (what must be TRUE):
  1. User clicks "Preview orders" in the Streamlit app, sees a table of intended orders, clicks "Confirm & submit" — orders only submit on the explicit confirm click
  2. With `DRY_RUN=true` (default in `.env.example`) the Preview flow completes and `logs/orders.csv` records the intended orders but the Alpaca account shows zero new orders
  3. Creating a `KILL_SWITCH` file at the repo root halts all order submission within the next run with a clear log message
  4. `pytest -p no:cacheprovider tests/test_bot_import.py` passes with sockets disabled — `import bot` makes zero network calls
  5. An attempt to submit > `MAX_ORDERS_PER_DAY` or an order > `MAX_ORDER_USD` is rejected with a clear error, not silently truncated
**Plans:** TBD
**Risks (HIGH-severity pitfalls to mitigate this phase):**
  - Pitfall #2 (Idempotency) — reinforced across daily reruns
  - Pitfall #7 (Timezone) — `trading_day_today()` used for every order id and cap counter
  - Pitfall #8 (Missing kill switch) — hard caps + `KILL_SWITCH` + `DRY_RUN` default
  - *(Pitfall #20 Trade-on-startup — MEDIUM-HIGH, mitigated by `test_bot_import_no_network`)*
**Test coverage delivered (from RH-01 safety floor):** #7 `test_bot_import_no_network`

### Phase H: Jev Signal Backend
**Goal:** `JevBackend` conforms to `SignalBackend`, HTTP calls are mockable, and the Streamlit explorer renders a RandomForest-vs-Jev side-by-side comparison on the same universe/period.
**Mode:** mvp
**Depends on:** Phase A (SignalBackend Protocol) — nothing else
**Parallel with:** Phases D, E, F, G — all four can run alongside H once A ships (per `research/ARCHITECTURE.md` §Suggested Build Order "Phase H: ... parallel-able with D–G")
**UI hint:** yes
**Requirements:** JV-01, JV-02, JV-03, JV-04, JV-05, JV-06
**Success Criteria** (what must be TRUE):
  1. `JevBackend.predict_proba_up(df)` returns a `pd.Series[float]` with values in `[0, 1]`, aligned to `df.index` — no SDK `Choice`/`Score` types leaked
  2. `pytest tests/test_jev_backend.py` passes with HTTP mocked — no live Jev API calls occur during the test suite
  3. User toggles the backend selector in the Streamlit UI and sees RF vs Jev metrics in a side-by-side layout on the same universe/date range
  4. `requirements.txt` pins `typesafe-sdk==1.3.*` exact-minor and `JevBackend` pins the model alias (not `jev-latest`)
  5. Running a backtest over 10 years of history with `backend=random_forest` makes zero Jev API calls (Jev is live-scoring only per JV-06)
**Plans:** TBD
**Risks (HIGH-severity pitfalls to mitigate this phase):**
  - *(No HIGH pitfalls directly — Jev's own severity is MEDIUM per PITFALLS.md §Moderate: #11 SDK breakage, #12 cost spikes)*
  - MEDIUM pitfalls to mitigate: #11 exact-minor pin + mocked HTTP tests, #12 Jev for live scoring only, #26 Protocol boundary prevents vendor lock-in
**Test coverage delivered (from RH-01 safety floor):** #6 `test_jev_backend_mocked_http`

---

## Cross-Phase: Reliability & Honesty (verified at milestone close)

**Requirements:** RH-01, RH-02, RH-03, RH-04
**Verified at:** milestone close via `/gsd:complete-milestone`
**Not a standalone phase** — these are hygiene requirements each phase contributes to; final audit happens at the end.

- RH-01: 10 anti-regression tests from PITFALLS.md "mentor-demo safety floor" (distributed across phases above)
- RH-02: README updated with CLI + Streamlit + bot usage
- RH-03: `.env.example` is the single source of truth for env vars
- RH-04: `.gitignore` audited (`.env`, `KILL_SWITCH`)

**Phase-to-test mapping (RH-01):**

| # | Test | Lands in |
|---|---|---|
| 1 | `test_paper_endpoint_assertion` | Phase F |
| 2 | `test_idempotent_submission` | Phase F |
| 3 | `test_portfolio_sharpe_math` | Phase D |
| 4 | `test_portfolio_sharpe_not_average_of_per_ticker` | Phase D |
| 5 | `test_trading_day_timezone` | Phase F |
| 6 | `test_jev_backend_mocked_http` | Phase H |
| 7 | `test_bot_import_no_network` | Phase G |
| 8 | `test_settings_repr_redacted` | Phase B |
| 9 | `test_order_cap_enforced` | Phase E |
| 10 | `test_dry_run_short_circuit` | Phase E |

All 10 must be green for mentor demo. Verified in milestone close.

---

## Dependency Graph

```
         ┌─── Phase A (SignalBackend) ──── load-bearing gate ───┐
         │                                                       │
         ▼                                                       ▼
    Phase B (Config)                                        Phase H (Jev)
         │                                                   (parallel w/ D–G)
         ▼
    Phase C (Streamlit single-ticker)
         │
         ▼
    Phase D (Multi-ticker) ──────────┐
         │                            │
         ▼                            │
    Phase E (Broker Protocol) ◀──┐    │
         │                       │    │
         ▼                       │    │
    Phase F (Alpaca adapter)     │    │
         │                       │    │
         ▼                       │    │
    Phase G (EOD bot loop) ◀─────┘ ◀──┘
```

- **A blocks everything.** No phase starts before A ships.
- **H is parallelizable with D–G** once A ships (per `research/ARCHITECTURE.md`).
- **B unblocks C and E** in sequence.
- **E must land before F**, F must land before G.
- **D must land before G** (bot uses the cross-sectional ranker).

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| A. SignalBackend Protocol | 0/1 | Not started | - |
| B. Config & Universe | 0/0 | Not started | - |
| C. Streamlit Single-Ticker Explorer | 0/0 | Not started | - |
| D. Multi-Ticker Cross-Sectional | 0/0 | Not started | - |
| E. Broker Protocol + FakeBroker | 0/0 | Not started | - |
| F. Alpaca Paper Adapter | 0/0 | Not started | - |
| G. EOD Bot Loop | 0/0 | Not started | - |
| H. Jev Signal Backend | 0/0 | Not started | - |

Plan counts fill in via `/gsd:plan-phase <phase>`.

---

## Open Design Questions (deferred to phase planning)

Per `.planning/REQUIREMENTS.md` §Traceability — resolved during the specific phase's `/gsd:plan-phase`:

- **TimeInForce policy** (OPG vs CLS vs DAY) — resolved in Phase F planning (recommendation: next-day open / `TimeInForce.OPG`)
- **Pooled vs per-ticker model architecture** — resolved in Phase D planning
- **Jev pricing / model alias confirmation** — resolved in Phase H planning

---

## Coverage Summary

| Phase | REQ-IDs | Count |
|---|---|---|
| A | SB-01, SB-02, SB-03, SB-04 | 4 |
| B | CU-01, CU-02, CU-03, CU-04, CU-05 | 5 |
| C | UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08 | 8 |
| D | MT-01, MT-02, MT-03, MT-04, MT-05, MT-06 | 6 |
| E | BR-01, BR-02, BR-03, BR-04 | 4 |
| F | AP-01, AP-02, AP-03, AP-04, AP-05, AP-06 | 6 |
| G | BL-01, BL-02, BL-03, BL-04, BL-05, BL-06, BL-07 | 7 |
| H | JV-01, JV-02, JV-03, JV-04, JV-05, JV-06 | 6 |
| Cross-phase (RH) | RH-01, RH-02, RH-03, RH-04 | 4 (hygiene, verified at close) |

**Total:** 38 phase-mapped + 4 cross-phase = **42/42 v1 REQ-IDs** ✓
No orphans. No duplicates.

---

*Roadmap for Stock-AI v1 milestone. Generated 2026-10-07.*

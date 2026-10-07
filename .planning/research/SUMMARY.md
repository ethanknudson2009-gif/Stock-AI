# Project Research Summary

**Project:** Stock-AI
**Domain:** Automated EOD paper-trading bot + Streamlit backtest explorer (multi-ticker US equities, Jev + RandomForest signals, Alpaca paper broker)
**Researched:** 2026-10-06
**Confidence:** MEDIUM-HIGH

## Executive Summary

Stock-AI v1 is an end-of-day, multi-ticker paper-trading bot wrapped in a Streamlit backtest explorer, built on top of the existing yfinance → scikit-learn → honest-backtest pipeline. The four research files converge on a single clean plan: keep `stock_ai/` as a pure library, add a thin **SignalBackend Protocol** so RandomForest and Jev are interchangeable, add a thin **Broker Protocol** so Alpaca is isolated behind a port, and ship the UI and the bot as thin consumers at the project root. Secrets go in `.env` only (no `st.secrets`), the Jev SDK is exact-minor pinned (`typesafe-sdk==1.3.*`), and the paper endpoint is asserted at construction so a live-trading accident is architecturally impossible.

The recommended build order (A → H) is dependency-driven: the SignalBackend Protocol lands first because it unblocks everything; config/universe land next; the Streamlit single-ticker explorer gives a visible win fast; multi-ticker + portfolio math and the broker abstraction follow; the Alpaca adapter and EOD bot loop ship next; Jev lands last because PROJECT.md Risk #1 flags it as the riskiest unknown — if Jev disappoints, every earlier phase still ships real value.

The dominant risks are (1) accidental live-endpoint hits, (2) non-idempotent order submission caused by Streamlit reruns or cron retries, (3) subtly dishonest "average-of-per-ticker-Sharpes" portfolio math, (4) survivorship bias in a hard-coded universe, and (5) timezone confusion between local time and US/Eastern market hours. All five are preventable with the architectural choices below plus a required set of 10 anti-regression pytest tests.

## Key Findings

### Recommended Stack

Minimal set of additions on top of the existing Python 3.12 / pandas / numpy / scikit-learn / yfinance / pytest stack. Streamlit + Plotly for the UI, `alpaca-py` for the broker (paper only), `typesafe-sdk` for Jev, `python-dotenv` for secrets. Full details and version pins in `.planning/research/STACK.md`.

**Core technologies (new in v1):**
- **`streamlit>=1.58,<2.0`** — browser UI; `streamlit run app.py`; fastest beginner path, pandas-native.
- **`plotly>=6.6,<7.0`** — interactive price charts with buy/sell markers; required by PROJECT.md.
- **`alpaca-py>=0.43,<0.50`** — official Alpaca SDK; `TradingClient(paper=True)` is the only entry.
- **`typesafe-sdk==1.3.*`** — Jev client; **exact-minor pin** is non-negotiable due to documented breaking changes between minors; pin model alias `jev-1.13` separately.
- **`python-dotenv>=1.0`** — single source of truth for secrets; already in `requirements.txt`, finally wired up.

**Secrets policy (locked):** `.env` only. No `st.secrets`. `load_dotenv()` called exactly once per entry point. All config read through `stock_ai/config/settings.py`. Scattered `os.environ.get(...)` calls are an anti-pattern.

### Expected Features

Full feature taxonomy and MVP checklist in `.planning/research/FEATURES.md`.

**Must have (table stakes — v1 scope):**
- Streamlit shell with ticker/date/threshold/cost inputs and headline-metrics output.
- Equity curve + price chart with buy/sell markers; trade-log table + CSV export.
- **Max drawdown** metric (gap in current engine — cheap to add).
- Multi-ticker **cross-sectional top-N ranker** on a 20–50 ticker universe.
- **Portfolio-level** return/Sharpe math — not an average of per-ticker Sharpes.
- Config file for universe, caps, params.
- RandomForest + Jev both selectable, side-by-side comparison panel.
- Alpaca paper client with paper-endpoint assertion; "Preview → Confirm → Submit" flow; idempotent `client_order_id` keyed on date+ticker.
- Per-order $ cap, daily-max-orders cap, `DRY_RUN` flag (default true in `.env.example`), `KILL_SWITCH` file.
- Account/positions/orders view in UI.
- Order log CSV + structured logging; README with 3-command demo.
- pytest coverage for the 10 safety invariants below.

**Should have (v1.x polish — adds mentor credibility):**
- Underwater (drawdown) chart, rolling Sharpe, hit-rate / win-loss stats.
- Per-ticker PnL contribution, SPY benchmark overlay, signal-stability check.
- Save/load named backtest runs.

**Defer (v2+):**
- Walk-forward with rolling retrain (single highest-value honesty upgrade).
- Bootstrap Sharpe CI; risk layer (vol targeting, drawdown halts, portfolio caps).
- Model persistence (joblib); LLM news/filings sentiment; per-ticker spread cost models; scheduled daily run (cron).
- Explicitly out of scope: live trading, intraday, options/futures/crypto, shorting, leverage, multi-user, mobile.

### Architecture Approach

The existing codebase is a **linear pandas pipeline of pure functions**. v1 keeps that character: `stock_ai/` stays a pure library, and `app.py`, `bot.py`, and the existing `main.py` are thin entry points at the project root that import *from* `stock_ai/` and never the reverse. Streamlit NEVER leaks into `stock_ai/`. Alpaca is only imported in `stock_ai/execution/paper.py`. Jev is only imported in `stock_ai/models/jev_backend.py`.

**Major components (new):**
1. **`stock_ai/models/base.py` — `SignalBackend` Protocol.** The contract both RF and Jev implement (`name`, `fit`, `predict_proba_up`). Consumers depend only on the Protocol; no `if backend == "jev"` branching anywhere.
2. **`stock_ai/execution/broker.py` — `Broker` Protocol + `AlpacaPaperBroker` + `FakeBroker`.** Hexagonal-lite. Unit tests inject `FakeBroker`; the Alpaca adapter is the single file to patch when the SDK bumps.
3. **`stock_ai/strategy/ranker.py` + `stock_ai/backtest/multi_engine.py`.** Cross-sectional top-N selection and portfolio-return aggregation. Composes over existing `engine.run_backtest`, does not replace it.
4. **`stock_ai/config/settings.py` + `stock_ai/universe/tickers.py`.** Single dotenv-backed Settings dataclass; curated large-cap universe (ADV > $50M) with explicit survivorship-bias docstring.
5. **`app.py`, `bot.py`, `ui/charts.py`.** Thin entry points + pure Plotly figure builders. `main.py` continues to work unchanged.

### Critical Pitfalls (top 5 — roadmap MUST plan for these)

From `.planning/research/PITFALLS.md` top-10. Full list of 26 pitfalls plus phase-specific warnings there.

1. **Live Alpaca endpoint by accident (Phase F).** Mitigation: `AlpacaPaperBroker.__init__` passes `paper=True` AND asserts `"paper-api"` is in the SDK's base URL at construction; UI banner shows the active endpoint; a dedicated pytest guards it.
2. **Non-idempotent order submission (Phase G).** Streamlit reruns + cron retries double-fill. Mitigation: deterministic `client_order_id = f"{eastern_date}_{ticker}_{side}"`, Alpaca 422-duplicate caught and returned as no-op, two-step Preview → Confirm UI, pytest asserts same `client_order_id` yields one submission.
3. **Averaging per-ticker Sharpes instead of portfolio Sharpe (Phase D).** Inflates reported Sharpe by ~√N and a mentor will spot it in 10 seconds. Mitigation: `multi_engine` computes a true portfolio return series with `weight_i * return_i` and turnover costs; pytest with 3 synthetic tickers vs hand-calc; UI labels the metric "Portfolio Sharpe (equal-weight top-N, daily rebalance)".
4. **Survivorship bias in the universe (Phase B, D).** Fixed "today's top 50" universe silently excludes delisted losers. Mitigation: document bias loudly in `universe/tickers.py` docstring, UI tooltip, and README; default backtest window = 3 years to bound bias; SPY overlay; point-in-time membership deferred to v2.
5. **Timezone confusion — US/Eastern vs local (Phase F, G).** Running `bot.py` at local-midnight breaks `client_order_id` dates and may fire with market still open. Mitigation: hard-code `zoneinfo.ZoneInfo("America/New_York")` for every trading-day decision via `trading_day_today()` helper; refuse submission when `clock.is_open`; pytest with frozen clock at 11:59pm PT asserts next-day ET date.

Also budget for: Streamlit rerun re-training (Pitfall 6, Phase C), `st.secrets` vs `.env` double-source confusion (Pitfall 9), secret leakage in Streamlit tracebacks (Pitfall 10), missing kill switch / spray-of-orders (Pitfall 8), `typesafe-sdk` breaking minors (Pitfall 11).

### Required Minimum Test Coverage (10 anti-regression tests)

These 10 pytest tests are non-negotiable for v1 mentor-demo readiness (verbatim from `PITFALLS.md` §Verification Discipline):

1. `test_paper_endpoint_assertion` — `AlpacaPaperBroker` refuses non-paper URL.
2. `test_idempotent_submission` — `FakeBroker` + same `client_order_id` = one submission.
3. `test_portfolio_sharpe_math` — 3-ticker synthetic case matches hand-calculated series.
4. `test_portfolio_sharpe_not_average_of_per_ticker` — explicit anti-regression on the Pitfall 3 math trap.
5. `test_trading_day_timezone` — frozen clock at 11:59pm PT returns the next ET date.
6. `test_jev_backend_mocked_http` — recorded 2026-10 fixture reproduces a known Series (mock at HTTP boundary, not at `JevBackend`).
7. `test_bot_import_no_network` — `import bot` makes zero network calls (use `pytest-socket`).
8. `test_settings_repr_redacted` — secrets never appear in `repr(Settings)`.
9. `test_order_cap_enforced` — `execution/orders.diff()` with over-cap target returns a capped order.
10. `test_dry_run_short_circuit` — `DRY_RUN=true` means no `broker.submit_order` call.

Each phase's exit criteria must include its share of these tests (see per-phase mapping below).

## Implications for Roadmap

The four research files converge on an 8-phase build order (A–H) that is dependency-driven, incrementally demo-able, and quarantines the single biggest unknown (Jev) to last.

### Phase A: SignalBackend Protocol
**Rationale:** Blocks everything downstream — doing this first avoids a mid-project refactor. The Protocol is the swap point for RF↔Jev that PROJECT.md requires.
**Delivers:** `stock_ai/models/base.py` (Protocol), `stock_ai/models/rf_backend.py` (wraps existing classifier), refactored `generate_signals(backend: SignalBackend, df, threshold)`, `main.py` wired through `RandomForestBackend()`.
**Addresses:** Table-stakes model-toggle feature; preserves backward compatibility with existing tests.
**Avoids:** Anti-Pattern 3 (special-casing Jev in `generate_signals`).
**Exit tests:** existing suite stays green + new `test_rf_backend.py`.

### Phase B: Config + Universe
**Rationale:** Small, independent, unblocks the UI and the broker. One place to read `.env`; one place to curate the universe.
**Delivers:** `stock_ai/config/settings.py` (dotenv-backed `Settings` dataclass with redacted `__repr__`), `stock_ai/universe/tickers.py` (default 20–50 large-cap list, ADV > $50M, survivorship docstring), `.env.example` populated.
**Addresses:** Secrets hygiene (table stakes), universe curation.
**Avoids:** Pitfall 4 (survivorship), 9 (`st.secrets` double-source), 10 (secret leakage via `repr`), 17 (illiquid universe), Anti-Pattern 5 (scattered `os.environ`).
**Exit tests:** `test_settings_repr_redacted` (test #8).

### Phase C: Streamlit Explorer — single-ticker
**Rationale:** Earliest visible win. Validates `app.py`/`ui/charts.py` separation before multi-ticker complexity.
**Delivers:** `app.py` + `ui/charts.py`; form inputs → single-ticker backtest → metrics + Plotly price-with-signals chart; `@st.cache_data` on fetch, `@st.cache_resource` on model, `st.form` wrapping slow widgets, `showErrorDetails = false`.
**Addresses:** Streamlit shell, equity curve, trade log, max drawdown metric (added here).
**Avoids:** Pitfall 6 (rerun thrash), 10 (traceback secret leakage), 16 (session-state inconsistency), 19 (stale cache), Anti-Pattern 1 (Streamlit creep into `stock_ai/`).
**Exit tests:** chart builders unit-tested via `figure.to_dict()`.

### Phase D: Multi-ticker Ranking + Portfolio Backtest
**Rationale:** Depends on A + B. The headline capability of v1. Portfolio-return math is a quiet dependency that must land here, not glossed over.
**Delivers:** `stock_ai/strategy/ranker.py` (pure top-N), `stock_ai/backtest/multi_engine.py` (true portfolio-return series with turnover costs), UI extended to accept comma-separated tickers + top-N, canonical NYSE trading-day index via `pandas_market_calendars` or SPY-indexed reference.
**Addresses:** Multi-ticker cross-sectional ranking + honest portfolio Sharpe (both table stakes).
**Avoids:** Pitfall 3 (avg-of-Sharpes — the big one), 5 (data alignment / holiday NaN), 18 (universe churn / mid-backtest delisting), 21 (Plotly perf on long series), Anti-Pattern 4 (reinventing backtest for multi-ticker).
**Exit tests:** `test_portfolio_sharpe_math` (#3), `test_portfolio_sharpe_not_average_of_per_ticker` (#4).

### Phase E: Broker Protocol + FakeBroker
**Rationale:** Lands before the Alpaca SDK dependency so the bot-loop logic is fully testable without network. Mirrors the testing culture of the existing codebase.
**Delivers:** `stock_ai/execution/broker.py` (Protocol), `stock_ai/execution/orders.py` (frozen `Order`, pure `diff(positions, targets, caps)` helper enforcing per-order $ cap), `stock_ai/execution/fake.py` (`FakeBroker` in-memory double).
**Addresses:** Idempotency contract, per-order cap, daily-max-orders cap plumbing.
**Avoids:** Pitfall 2 (non-idempotent — enforced by FakeBroker tests), 8 (kill switch / caps enforced in `diff()`), 20 (trade-on-startup — Protocol forces explicit injection), Anti-Pattern 2 (mocking the SDK instead of using a port).
**Exit tests:** `test_order_cap_enforced` (#9), seed for `test_idempotent_submission` (#2).

### Phase F: Alpaca Adapter
**Rationale:** Isolates all `alpaca-py` imports behind the Protocol. Only one file to patch when `alpaca-py` renames request models in a minor bump.
**Delivers:** `stock_ai/execution/paper.py` with `AlpacaPaperBroker`; hard-coded `paper=True`; construction-time assertion that `"paper-api"` is in the SDK's base URL; pre-flight `get_asset`/`get_clock`/`get_account` checks; 422-duplicate caught as idempotent no-op; TimeInForce policy decision (**OPEN QUESTION — see Gaps**); rate-limit pacing (`time.sleep(0.1)` between orders); `normalize_symbol` helper for `BRK.B`/`BRK/B`.
**Addresses:** Paper-trading loop plumbing, account/positions/orders view.
**Avoids:** Pitfall 1 (live endpoint), 13 (rate limit 200 req/min), 14 (rejections — fractional, non-tradable, PDT), 15 (extended-hours fill timing), 24 (cash vs buying_power).
**Exit tests:** `test_paper_endpoint_assertion` (#1), `test_idempotent_submission` (#2).

### Phase G: EOD Bot Loop
**Rationale:** Depends on A + D + F. The actual bot action, with the full safety stack layered on.
**Delivers:** `bot.py` with `run_eod(backend, broker=None, ...)` taking injected broker; US/Eastern `trading_day_today()` helper; `client_order_id` keyed on Eastern date + ticker + side; `DRY_RUN` flag (default true in `.env.example`); `KILL_SWITCH` file check; degenerate-signal gate (`stddev(scored) < 0.01` → abort); verbose per-decision rationale log; Streamlit "Place paper orders for today" page with Preview → Confirm → Submit flow.
**Addresses:** The bot (table stakes), kill switches, idempotent submission, order log CSV.
**Avoids:** Pitfall 2, 7 (timezone), 8 (spray-of-orders), 20 (trade-on-startup).
**Exit tests:** `test_trading_day_timezone` (#5), `test_bot_import_no_network` (#7), `test_dry_run_short_circuit` (#10).

### Phase H: Jev Backend
**Rationale:** Last on purpose. PROJECT.md Risk #1 flags Jev as unproven; everything upstream ships real value on RandomForest if Jev disappoints. All Jev concerns are isolated behind `SignalBackend` and the `jev_backend.py` file.
**Delivers:** `stock_ai/models/jev_backend.py` conforming to Protocol; `typesafe-sdk==1.3.*` exact-minor pin; model alias `jev-1.13` pinned; UI backend-selector dropdown; side-by-side RF vs Jev comparison panel; Jev used for **live scoring only**, not full historical backtest (cost control); disk cache keyed by feature-vector hash + model version; HTTP-boundary mocking in tests.
**Addresses:** Jev integration (PROJECT.md hard requirement), honest RF-vs-Jev comparison.
**Avoids:** Pitfall 11 (SDK breaking minors), 12 (latency / cost), 23 (non-determinism), 26 (vendor lock-in — only `jev_backend.py` touches Jev types).
**Exit tests:** `test_jev_backend_mocked_http` (#6).

### Phase Ordering Rationale

- **A first** because the Protocol is the swap point every downstream phase needs; introducing it mid-project would force a refactor.
- **B second** because config + universe are cheap, unblocking, and set the secrets policy before any UI or broker code can leak secrets.
- **C before D** because a visible single-ticker UI is a demo-able checkpoint; multi-ticker is a logical extension, not a precondition.
- **E before F** because unit-testable broker logic should land before any SDK dependency, matching the existing "pure core, network at the edge" testing culture.
- **G after F** because the bot loop composes the broker + ranker + backend; it can only exist once its three dependencies are stable.
- **H last** because Jev is the single biggest unknown and the project must ship real value even if Jev doesn't materialize.

### Research Flags

**Phases that likely need `/gsd:plan-phase --research-phase` deep-dives:**
- **Phase F (Alpaca adapter):** TimeInForce policy decision (`DAY` vs `OPG` vs `CLS`) is an open design choice; also fractional-share and symbol-normalization edge cases need SDK-version-specific validation.
- **Phase H (Jev backend):** `typesafe-sdk` 1.3.x API surface (exact import paths, batch support, `seed` parameter availability) must be confirmed against the live SDK before implementation; Jev model pricing/call cadence must be validated to size the live-scoring-only cache strategy.
- **Phase D (Multi-ticker):** The "pooled model vs per-ticker ensemble" decision is still open — see Gaps below.

**Phases with standard patterns (skip deep research, follow architecture.md):**
- Phase A (Protocol + dataclass wrapper — PEP 544 standard).
- Phase B (dotenv + dataclass — well-trodden).
- Phase C (Streamlit form + cache — docs-driven).
- Phase E (hexagonal-lite with Protocol + fake — pattern locked in `ARCHITECTURE.md`).
- Phase G (compose A + E + F — architectural plumbing, no new research needed).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Streamlit/Plotly/alpaca-py are well-established; `typesafe-sdk` is young (2026 launch) with documented breaking-minor history — mitigated by exact-minor pin. |
| Features | MEDIUM-HIGH | Backtest-UI + paper-trading feature conventions are well-codified in OSS (Backtrader, VectorBT, Freqtrade, Alpaca examples); Jev-specific features are MEDIUM. |
| Architecture | HIGH | Protocol-based SignalBackend, hexagonal-lite Broker, and thin-entrypoint patterns are standard and align with the existing linear-pipeline codebase. |
| Pitfalls | HIGH | Alpaca/Streamlit/multi-ticker pitfalls are documented in SDK docs and quant literature; Jev-specific pitfalls are MEDIUM but mitigated by HTTP-boundary mocking and exact-minor pinning. |

**Overall confidence:** MEDIUM-HIGH. The architecture and build order are solid; the two residual risks are (a) Jev being unsuitable for daily-EOD US-equity direction prediction (PROJECT.md Risk #1 — mitigated by always keeping the RF baseline wired) and (b) `typesafe-sdk` breaking under us during the milestone (mitigated by exact-minor pin + HTTP-boundary tests).

### Gaps to Address (open questions — resolve during Phase planning)

1. **TimeInForce policy for Phase F.** v1 must pick ONE of: `TimeInForce.DAY` queued-for-next-open, `TimeInForce.OPG` (next-session open), or `TimeInForce.CLS` (today's close, submitted before ~3:50pm ET). Research recommends **next-day open (`OPG`)** for simplicity and backtest-reconciliation symmetry, but this is a locked design decision owner should ratify before Phase F planning. The backtest engine's assumed fill-price convention must align with the chosen policy.
2. **Jev pricing / `jev-1.13` alias / batch support confirmation for Phase H.** Research assumes `jev-1.13` is accepted by `typesafe-sdk==1.3.*` and that per-call cost is in the $0.001–$0.01 range; both need to be confirmed against TypeSafe's live docs during Phase H planning. If batch inference is unsupported, the live-scoring-only strategy is required (not optional).
3. **Pooled model vs per-ticker ensemble for Phase D.** FEATURES.md flags this as a design decision needed before multi-ticker ranking can be implemented. A single pooled model (with ticker-dummy features) is simpler and more honest for a 50-ticker universe; per-ticker ensemble is closer to the current single-ticker pipeline but 50× the training cost. Research leans **pooled** for v1 but owner should decide at Phase D kickoff.

## Sources

### Primary (HIGH confidence)
- `.planning/research/STACK.md` — pinned versions, auth patterns, `.env` policy.
- `.planning/research/ARCHITECTURE.md` — SignalBackend/Broker Protocols, phase order A–H.
- `.planning/research/FEATURES.md` — table-stakes feature list, MVP checklist, feature dependencies.
- `.planning/research/PITFALLS.md` — 26 pitfalls, phase-specific warnings, 10-test coverage floor.
- `.planning/PROJECT.md` — locked decisions, risk register, scope boundaries.
- `.planning/codebase/{ARCHITECTURE,STRUCTURE,CONVENTIONS,CONCERNS}.md` — existing linear-pipeline shape.
- Alpaca `alpaca-py` official docs — paper endpoint, `client_order_id`, `TimeInForce`, rate limits.
- Streamlit official docs — `@st.cache_data`, `@st.cache_resource`, `st.form`, `showErrorDetails`.
- PEP 544 — structural subtyping / Protocol.

### Secondary (MEDIUM confidence)
- openclawdatabase.com, llmreference.com, composio.dev on TypeSafe Jev — SDK breakage history, model aliases.
- Lopez de Prado, *Advances in Financial ML* — survivorship, alignment, portfolio Sharpe discipline.
- Cosmic Python / *Architecture Patterns with Python* — hexagonal / ports-and-adapters.
- Backtrader / VectorBT / Freqtrade community conventions — DRY_RUN, kill-switch, order-log patterns.

### Tertiary (LOW confidence)
- Jev per-call pricing estimates ($0.001–$0.01) — inferred from 2026 release notes; must be validated during Phase H planning.

---
*Research completed: 2026-10-06*
*Ready for roadmap: yes*

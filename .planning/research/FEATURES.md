# Feature Research

**Domain:** Automated paper-trading bot + Streamlit backtest explorer (daily EOD, multi-ticker US equities, Jev + RandomForest signals, Alpaca paper broker)
**Researched:** 2026-10-06
**Confidence:** MEDIUM-HIGH (feature set is well-codified in open-source trading ecosystems — Backtrader, VectorBT, QuantConnect, Alpaca examples, Freqtrade; Jev-specific features are MEDIUM confidence)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features without which the project does not meet the "paper-trading bot you can show mentors" bar.

#### (a) Streamlit Backtest Explorer UI

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Ticker input (single or multi) with date-range picker | Universal in every backtest UI (QuantConnect, Backtrader, Composer, Tiingo) | LOW | `st.text_input` / `st.multiselect` + `st.date_input`. Default universe from config. |
| Strategy knobs (confidence threshold, cost in bps, top-N) | Users must be able to see how sensitivity changes outcomes | LOW | `st.slider` + `st.number_input`. Match CLI flags. |
| "Run Backtest" button with progress indicator | Long operations (multi-ticker fetch + train) need feedback | LOW | `st.button` + `st.spinner` or `st.progress`. |
| Headline metrics panel: OOS return, buy-hold return, Sharpe, trade count, hit rate, max drawdown | Table stakes for ANY backtest tool; mentors will immediately look for Sharpe + drawdown | LOW | `st.metric` grid. Max drawdown is required but not yet in codebase — small add. |
| Equity curve chart (strategy vs buy-and-hold overlay) | #1 visual every backtest dashboard shows | LOW | Plotly line chart; two series. |
| Price chart with buy/sell markers | Already in v1 scope; standard in Backtrader/VectorBT viewers | LOW | Plotly candlestick or line + scatter markers from position-change dates. |
| Trade log table (date, ticker, side, price, size, pnl) | Required for auditing — "show me the trades" is the first mentor question | LOW | `st.dataframe` with CSV download. |
| In-sample vs out-of-sample side-by-side | PROJECT.md requires it; prevents dishonesty | LOW | Two columns of metrics or tabs. |
| Model-choice toggle (RandomForest / Jev) | Required by PROJECT.md for honest comparison | LOW | `st.radio` or `st.selectbox`. |
| Error surfacing (bad ticker, empty data, API failure) | Currently crashes with traceback — unacceptable in a demo UI | LOW | `try/except` + `st.error()`. |

#### (b) Alpaca Paper-Trading Loop

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| API key loading from `.env` with explicit missing-key error | Standard pattern; prevents demo-day embarrassment | LOW | `python-dotenv` + friendly error. |
| Paper-endpoint hard-coding (never live-endpoint) | Safety-critical — must be impossible to accidentally hit live API | LOW | Hard-code `paper-api.alpaca.markets` + assert in init. |
| Market-open / tradable-asset check before order submission | Alpaca rejects orders when market closed; UX must preempt | LOW | `clock` endpoint; `asset.tradable` check. |
| Submit market orders for today's signals (per-ticker, bracketable) | The core bot action | MEDIUM | `alpaca-py` `MarketOrderRequest` with `TimeInForce.DAY`. |
| Position-sizing rule (fixed-$ or equal-weight across top-N) | Can't just send `qty=1` for a bot that "trades a universe"; mentors will ask | LOW | Equal-weight: `cash * (1/N) / price`, floor to whole shares. |
| Position & account view: cash, equity, buying power, open positions, today's orders | Table stakes — every broker dashboard shows this | LOW | `trading_client.get_account()` + `get_all_positions()` → Streamlit table. |
| Idempotent "signals-for-today" generation (same input → same signals, no duplicate orders if re-run) | Prevents double-ordering on refresh / rerun — Streamlit reruns on every widget change | MEDIUM | Use Alpaca `client_order_id` keyed on `{date}_{ticker}_{side}`; existing-order check before submit. |
| Order confirmation step in UI (preview → confirm) | No mentor wants a demo to accidentally submit 50 orders mid-explanation | LOW | Two-step: "Preview orders" button → table → "Submit" button. |
| Append-only trade/order log on disk (CSV or SQLite) | Required for debugging "what did the bot do last Tuesday?" | LOW | CSV append in `logs/orders.csv`. |

#### (c) Multi-Ticker Cross-Sectional Signal + Portfolio Construction

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Train one model (or one per ticker — pick ONE) on the universe | Cross-sectional is the only reason multi-ticker is in scope | MEDIUM | Recommend: single pooled model with ticker-dummy or per-ticker ensemble. Decision needed in design. |
| Rank candidates by model `predict_proba(up)` on each decision day | Core of cross-sectional strategy | LOW | `df.groupby('date').rank(ascending=False)`. |
| Top-N selection with configurable N (default 5–10 of 50) | Industry-standard construction (long-only momentum books) | LOW | Slice top N per date. |
| Equal-weight portfolio construction (long top-N, flat the rest) | Simplest honest baseline; matches v1 "no risk layer" stance | LOW | `weight = 1/N` for selected, 0 otherwise. |
| Rebalance cadence = daily (matches EOD cadence) | Consistent with decided cadence | LOW | Positions recomputed each decision day. |
| Universe config file (YAML or Python list) overridable in UI | PROJECT.md requires it | LOW | `config/universe.yaml` with default 50 tickers. |
| Portfolio-level backtest (not just per-ticker average) | Mentor will immediately ask: "what's the portfolio Sharpe?" — different from averaging per-ticker Sharpes | MEDIUM | Need per-day portfolio return = Σ(weight_i × return_i) − turnover_cost. New engine or extension. |

#### (d) General Bot Hygiene

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Secrets in `.env`, `.env.example` committed, `.env` in `.gitignore` | PROJECT.md requires it; public repo | LOW | Already in scope. |
| Config file for universe, costs, thresholds, position caps (not hard-coded) | Table stakes for ANY bot | LOW | `config.yaml` + pydantic or dataclass loader. |
| Per-order position cap (hard-coded $ or % ceiling) | PROJECT.md Risk #2 explicitly calls for this | LOW | e.g., `MAX_ORDER_USD = 1000` + assertion. |
| Daily-max-orders cap (kill switch #1) | Prevents runaway bot from spraying 100 orders on buggy signals | LOW | Count orders submitted today in CSV log; refuse above threshold. |
| Explicit "DRY_RUN" mode flag (prints orders without submitting) | Required for development & demos; standard in Freqtrade/Backtrader | LOW | Env var or CLI flag. |
| Structured logging (python `logging` with INFO/WARNING/ERROR to file + stdout) | Replaces `print()`; required for post-hoc debugging | LOW | One `setup_logging()` function. Rotate daily. |
| Verbose order rationale log (ticker, proba, rank, decision reason) | PROJECT.md Risk #2 mitigation; makes bot behavior auditable | LOW | One structured log line per decision. |
| README with install + 3-command demo (install, backtest, launch UI) | First impression for mentors | LOW | PROJECT.md requires it. |
| pytest coverage for new critical invariants: no live-endpoint call, idempotency, top-N selection, portfolio-return math | PROJECT.md requires test coverage for every new capability | MEDIUM | ~4–6 new tests. |

---

### Differentiators (Would Impress Mentors)

Nice-to-haves that elevate the project from "it works" to "wow, you thought about this."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Side-by-side RandomForest vs Jev results panel | Shows honest model comparison instead of just picking a winner | LOW | Already in PROJECT.md as a requirement — treat as differentiator-grade polish. |
| Save/load backtest runs (name + params + results archived) | Lets mentors browse "last Tuesday's run"; needed anyway to compare models fairly | MEDIUM | SQLite table or JSON blobs under `runs/`. |
| Per-ticker contribution breakdown (which tickers made/lost the money) | Reveals whether returns are concentrated or diversified — a sophisticated question | LOW | Sum per-ticker pnl across backtest. |
| Rolling Sharpe / rolling return chart | Shows regime behavior; standard in professional reporting | LOW | 63-day or 126-day rolling window. |
| Underwater (drawdown) chart | Universal pro visualization; one chart, big credibility boost | LOW | Plotly fill-area. |
| Hit-rate + average-win / average-loss stats | Classic trader-interview metrics | LOW | Derived from trade log. |
| Monte-Carlo / bootstrap confidence interval on Sharpe | Flagged as v2 but a MEDIUM-complexity version is tractable | MEDIUM | 1000 bootstrap resamples of returns. |
| Signal-stability check (does today's top-10 overlap with yesterday's?) | Reveals whether model is noise or signal — great talking point | LOW | Set intersection across adjacent decision days. |
| Walk-forward with rolling retrain | PROJECT.md v2 feature — the single most valuable backtest honesty upgrade | HIGH | Deferred, but even a 2-fold version would differentiate. |
| Scheduled daily run (cron / `apscheduler` from inside app) | Makes it a bot in practice, not just an on-demand script | MEDIUM | Simple: launchd/cron entry calling CLI. In-app scheduler is heavier. |
| Equity-vs-SPY benchmark overlay | More honest comparison than buy-and-hold of each ticker | LOW | Add SPY fetch + overlay. |
| Clear versioning of configs + model artifacts in run log | Reproducibility; mentors with ML background will notice | LOW | Hash of config + git SHA stored per run. |

---

### Anti-Features (Explicitly Out of Scope for v1)

Features that look obvious but create outsized complexity or safety risk for a 2–4 week beginner milestone. All reinforce PROJECT.md "Out of Scope."

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Live trading with real money | "Why paper if real exists?" | Months of paper-validation needed before live; real money + buggy Jev = real losses; one typo = real losses | Paper-only. Live is explicit v3+. |
| Intraday / minute-bar / tick trading | "Pros do intraday" | Streaming data, latency management, exchange rate limits; totally different architecture | Daily EOD only — matches cadence everywhere in codebase. |
| Options / futures / crypto / FX | "More instruments = more opportunities" | Each has its own margining, Greeks, settlement rules; Alpaca options are a separate SDK | US equities + ETFs only. |
| Short selling | "Long-only misses half the alpha" | Borrow fees, locates, forced buy-ins; margin complexity; unbounded loss | Long/flat only (already in signal.py). |
| Leverage / margin trading | "Easy returns boost" | Compounds Jev-risk; margin calls; broker-specific rules | 100% cash, no leverage. |
| Stop-loss / take-profit orders inside the strategy | "Risk management!" | Daily-EOD bot doesn't need intraday stops; adding them re-opens the risk-layer design PROJECT.md explicitly defers | Daily rebalance IS the exit; v2 risk layer. |
| Portfolio optimization (mean-variance, Kelly, risk parity) | "Pros optimize weights" | Requires covariance estimation on noisy returns; typically underperforms equal-weight on small universes | Equal-weight top-N; v2+ optimization. |
| Multi-user auth / cloud deployment / hosted dashboard | "Share with mentors remotely" | Streamlit auth + hosting is a separate project; `.env` secrets become a security problem on shared host | Local-only Streamlit; mentors run `git clone` + `streamlit run`. |
| Mobile responsive UI / mobile app | "Phone access" | Streamlit's mobile UX is weak; not worth tuning | Browser on laptop. |
| Real-time news/sentiment integration (FinGPT, LLM filings reader) | "LLMs are the hot layer" | PROJECT.md v2 defers this; adds LLM API costs, prompt engineering, and signal-validation work | Pure-price features in v1; LLM layer v2. |
| Alternative data (satellite, credit card, foot traffic) | "Alpha is in alt data" | Expensive, not free-tier, overkill for learning project | OHLCV only. |
| Custom Jev model training (not just inference) | "Fine-tune for us" | Research flags Jev as marketed for HFT; training APIs may not exist / have cost | Use Jev out of the box; fall back to RandomForest if underwhelming. |
| User-editable Python in UI (notebook-style code eval) | "Flexible exploration" | Code injection risk + Streamlit isn't a notebook | Params-only UI; mentors can read source. |
| Multiple broker backends (Alpaca + IBKR + TD + ...) | "Broker-agnostic!" | Each SDK is a project; v1 doesn't need portability | Alpaca paper only; abstract the client interface if cheap. |
| Automated hyperparameter search (GridSearchCV, Optuna) | "Model will perform better" | Guaranteed overfit on this little data; produces false confidence | Single hand-picked config; walk-forward in v2 is the honest tuning layer. |
| Live P&L email/SMS alerts | "Monitoring!" | Infra creep (SMTP creds, Twilio); not useful for a bot you'd watch anyway | Log file + Streamlit "today" page. |
| "Autopilot" mode that re-trains + trades without any human in the loop | "Fully automated bot" | Unsafe before validation; mentors should see the loop, not a black box | Manual "Run signals for today" button in v1. |

---

## Feature Dependencies

```
Streamlit UI shell
    └──requires──> Config loader (universe, params, caps)
    └──requires──> Error-handling wrapper on existing pipeline

Multi-ticker backtest
    └──requires──> Loader extension (batch fetch)
    └──requires──> Cross-sectional ranker
            └──requires──> Pooled model OR per-ticker loop
                    └──requires──> Portfolio-return engine (not just per-ticker avg)

Jev signal mode
    └──requires──> Jev client wrapper
    └──requires──> Feature-vector adapter (shared with RandomForest via FEATURE_COLUMNS)
    └──enhances──> Streamlit model-choice toggle
    └──enhances──> Side-by-side comparison panel

Alpaca paper trading
    └──requires──> Alpaca client wrapper (paper-endpoint hard-coded)
    └──requires──> Market-open / tradable check
    └──requires──> Position sizer (equal-weight across top-N)
    └──requires──> Order log (CSV append)
    └──requires──> Idempotency via client_order_id
    └──requires──> Per-order $ cap + daily-max-orders cap
            └──enables──> "Run today's signals" action in UI

Trade log + run log
    └──enables──> Trade table in UI
    └──enables──> Per-ticker contribution breakdown
    └──enables──> Hit-rate stats
    └──enables──> Reproducibility (differentiator)

DRY_RUN mode
    └──conflicts──> Live submission path (must branch cleanly on a single flag)

Portfolio-level backtest math
    └──conflicts──> Naive "average per-ticker Sharpe" reporting (pick ONE and label it)
```

### Dependency Notes

- **Multi-ticker ranker precedes Alpaca submission:** You cannot submit paper orders meaningfully until the cross-sectional top-N selection is defined. Order of build: Streamlit shell → multi-ticker + ranker on RandomForest → portfolio-return math → Alpaca submission → Jev swap-in last.
- **Jev last on purpose:** PROJECT.md Risk #1 flags Jev as unproven. Everything upstream must work on RandomForest first, so if Jev disappoints, the project still ships.
- **Idempotency requires persistence:** Order log must exist on disk before the "submit today's signals" button is safe to click twice.
- **Portfolio-return math is a quiet dependency:** Easy to overlook. Averaging per-ticker Sharpes gives a wrong, flattering number. The real portfolio-return calculation is MEDIUM complexity but critical for honesty.

---

## MVP Definition

### Launch With (v1 — mentor-demo-ready bar)

Minimum to meet the "paper-trading bot you can show mentors" promise.

- [ ] **Streamlit shell** with ticker/date/threshold/cost inputs and headline-metrics output — without this, there is no UI.
- [ ] **Equity curve + price chart with trade markers** — mandatory visual proof.
- [ ] **Trade log table + CSV export** — mandatory audit.
- [ ] **Max drawdown added to backtest metrics** — gap in current engine; cheap to add; mentor will ask.
- [ ] **Multi-ticker backtest with top-N cross-sectional ranker on 20–50 tickers** — the headline capability.
- [ ] **Portfolio-level return/Sharpe math (not per-ticker averaged)** — honesty-critical.
- [ ] **Config file for universe, params, caps** — bot hygiene.
- [ ] **RandomForest + Jev both selectable** with side-by-side results — PROJECT.md hard requirement.
- [ ] **Alpaca paper client wrapper with paper-endpoint assertion** — safety-critical.
- [ ] **"Preview today's orders → Confirm → Submit" flow** — the actual bot action, with a safety gate.
- [ ] **Idempotent order submission (`client_order_id` keyed on date+ticker)** — prevents demo disasters.
- [ ] **Per-order $ cap + daily-max-orders cap** — PROJECT.md Risk #2 mitigation.
- [ ] **Account/positions/orders view in UI** — mentor's second question after seeing a backtest.
- [ ] **Order log CSV + structured logging** — bot hygiene.
- [ ] **DRY_RUN flag** — safe demo mode.
- [ ] **pytest coverage for: paper-endpoint assertion, idempotency, top-N selection, portfolio-return formula** — PROJECT.md discipline.
- [ ] **README with 3-command demo (install, backtest, launch UI) + `.env.example`** — first impression.

### Add After Core Works (v1.x)

Trigger: core v1 demo lands and feels solid.

- [ ] Underwater (drawdown) chart — adds polish to the metrics panel.
- [ ] Hit-rate + win/loss stats — one derived table.
- [ ] Per-ticker contribution breakdown — great talking point.
- [ ] Rolling Sharpe chart — regime awareness.
- [ ] Save/load named backtest runs — enables fair A/B of Jev vs RF across time.
- [ ] SPY benchmark overlay — more honest comparison.
- [ ] Signal-stability (top-N overlap day-over-day) — reveals signal quality.

### Future Consideration (v2+ — matches PROJECT.md deferred list)

- [ ] Walk-forward with rolling retrain — single biggest honesty upgrade; HIGH complexity.
- [ ] Bootstrap confidence intervals on Sharpe — statistical rigor.
- [ ] Risk management layer (vol-targeted sizing, drawdown halts, portfolio caps) — explicitly v2.
- [ ] Model persistence (joblib save/load) — avoids retraining on every backtest.
- [ ] News/filings sentiment via LLM — PROJECT.md v2.
- [ ] Per-ticker transaction cost modeling — PROJECT.md v2.
- [ ] Scheduled daily run (cron) — turns on-demand into true bot.
- [ ] Secondary data source fallback (Alpaca market data) — PROJECT.md Risk #4.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Streamlit shell + headline metrics | HIGH | LOW | **P1** |
| Equity curve + price chart with markers | HIGH | LOW | **P1** |
| Max drawdown metric | HIGH | LOW | **P1** |
| Multi-ticker top-N ranker | HIGH | MEDIUM | **P1** |
| Portfolio-return math (not averaged) | HIGH | MEDIUM | **P1** |
| Trade log table + CSV | HIGH | LOW | **P1** |
| Config file (universe, caps, params) | HIGH | LOW | **P1** |
| Alpaca paper client (paper-endpoint locked) | HIGH | LOW | **P1** |
| Preview → Confirm → Submit flow | HIGH | LOW | **P1** |
| Idempotency via `client_order_id` | HIGH | MEDIUM | **P1** |
| Per-order cap + daily-max-orders cap | HIGH | LOW | **P1** |
| Account/positions/orders view | HIGH | LOW | **P1** |
| Order log CSV + structured logging | HIGH | LOW | **P1** |
| DRY_RUN flag | HIGH | LOW | **P1** |
| Jev client wrapper | HIGH | MEDIUM | **P1** |
| RF vs Jev side-by-side | HIGH | LOW | **P1** |
| pytest for safety invariants | HIGH | MEDIUM | **P1** |
| Underwater (drawdown) chart | MEDIUM | LOW | P2 |
| Rolling Sharpe chart | MEDIUM | LOW | P2 |
| Hit-rate / win-loss stats | MEDIUM | LOW | P2 |
| Per-ticker pnl contribution | MEDIUM | LOW | P2 |
| Save/load named runs | MEDIUM | MEDIUM | P2 |
| SPY benchmark overlay | MEDIUM | LOW | P2 |
| Signal stability check | MEDIUM | LOW | P2 |
| Walk-forward backtest | HIGH | HIGH | P3 (v2) |
| Bootstrap Sharpe CI | MEDIUM | MEDIUM | P3 (v2) |
| Risk layer (vol targeting, drawdown halts) | HIGH | HIGH | P3 (v2) |
| Model persistence | MEDIUM | LOW | P3 (v2) |
| News/LLM sentiment | MEDIUM | HIGH | P3 (v2) |
| Scheduled daily run (cron) | MEDIUM | LOW | P3 (v2) |

---

## Competitor / Reference Feature Analysis

| Feature | Backtrader / VectorBT (OSS backtest libs) | Alpaca example bots (GitHub) | QuantConnect / Composer (hosted) | Our v1 Approach |
|---------|------------------------------------------|------------------------------|----------------------------------|-----------------|
| Backtest explorer UI | None (code-only) or Jupyter widgets | Rare — mostly CLI scripts | Rich hosted UIs | Streamlit — lighter than QC, friendlier than Jupyter |
| Multi-ticker cross-sectional | VectorBT yes; Backtrader via custom | Occasional (crypto focused) | Yes, built-in | Yes, top-N equal-weight |
| Paper-trading hookup | Not native (library focus) | Built-in via alpaca-py | Yes, native | Native via alpaca-py |
| Idempotent order submission | N/A | Hit-or-miss in examples | Yes | `client_order_id` keyed on date+ticker |
| Dry-run / preview mode | Yes | Rare | Yes | Yes, DRY_RUN flag + preview-confirm step |
| Jev / custom-AI signal | N/A | Rare — mostly rules | QC has ML Lean modules | Jev wrapper + RF baseline toggle |
| Walk-forward / purged CV | VectorBT yes; Backtrader manual | No | Yes | **Deferred to v2** (differentiator window) |
| Risk layer (vol targeting, caps) | Manual | No | Yes | **Deferred to v2** (just hard caps in v1) |
| Position sizing | Flexible | Mostly fixed-$ | Flexible | Equal-weight top-N (simplest honest choice) |
| Order log | File-based (user wires it) | Script-local | Hosted | Local CSV append |
| Save/load runs | Pickle/JSON (manual) | No | Yes, hosted | Deferred to v1.x |

**Takeaway:** The combination most paper-trading tutorials miss is **(backtest UI) + (multi-ticker cross-sectional) + (safe paper submission with idempotency and caps)**. Any one of those is common; shipping all three in a readable solo-dev codebase is itself the differentiator.

---

## Mentor-Demo Readiness Checklist

The minimum feature slice that makes the project showable in a 10-minute mentor conversation:

1. **Launch** — `streamlit run app.py` opens a UI with no stack trace.
2. **Backtest** — Pick 3 tickers, hit Run, see metrics + equity curve + trade markers + trade log.
3. **Compare** — Toggle RandomForest → Jev; show side-by-side metrics panel.
4. **Universe** — Switch to 50-ticker universe, run cross-sectional backtest, see portfolio Sharpe + top contributors.
5. **Paper trade** — Click "Preview today's orders," confirm, see Alpaca account page update with positions.
6. **Audit** — Open `logs/orders.csv` and `logs/runs.csv` to show reproducibility.
7. **Safety** — Flip DRY_RUN flag, run again, show no live order was sent.

If any of steps 1–7 don't work on a cold `git clone`, the demo isn't ready.

---

## Sources

- PROJECT.md v1 scope and risk register (locked decisions)
- `.planning/codebase/ARCHITECTURE.md` (current pipeline shape — pure-function stages, in-memory only)
- General knowledge of backtest-tooling conventions:
  - Backtrader, VectorBT (OSS Python backtest libraries) — standard metrics and chart conventions
  - Freqtrade (crypto bot) — DRY_RUN, config, order-log, kill-switch patterns
  - Alpaca `alpaca-py` SDK docs — paper endpoint, `client_order_id` idempotency, `MarketOrderRequest`, `TradingClient.get_account`
  - QuantConnect / Composer dashboards — UI conventions (metrics panel, equity curve, trade log, drawdown chart, benchmark overlay)
  - Lopez de Prado "Advances in Financial ML" — walk-forward, bootstrap CI (flagged as v2 differentiators)

**Confidence notes:**
- HIGH on Streamlit, Alpaca paper, and backtest-UI feature conventions — these are well-codified in open-source examples and docs.
- MEDIUM on Jev-specific features — Jev is a 2026-era TypeSafe AI product and research flagged it as unproven for daily EOD equity prediction. Feature list assumes Jev exposes a classify/predict-with-probability endpoint; adapter layer should assume minimum surface area.
- MEDIUM on portfolio-return math — the "pick ONE and label it" caveat matters; averaging per-ticker Sharpes is a subtle, common dishonesty trap.

---
*Feature research for: automated paper-trading bot + Streamlit backtest explorer*
*Researched: 2026-10-06*

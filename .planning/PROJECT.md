# Stock-AI — Project

**Owner:** Bryan Dockstader (dockfam2019@gmail.com)
**Repository:** https://github.com/ethanknudson2009-gif/Stock-AI
**Status:** Active — v1 milestone in planning
**Last updated:** 2026-10-06 after initialization

---

## What This Is

A learning-by-building project aimed at a specific target: a **Jev-powered automated stock trading bot that paper-trades a broad universe of US equities on a daily cadence**, backed by a browser-based backtest explorer so decisions can be inspected before any paper order gets placed.

It starts from the existing Stock-AI Python codebase (yfinance → scikit-learn RandomForest → long/flat backtest) and grows it into a running bot connected to Alpaca's paper-trading sandbox, with Jev as the signal classifier replacing or augmenting the current RandomForest.

The underlying motivation is **learning algorithmic trading, AI integration, and real-world system plumbing by shipping something that actually runs** — not building an edge that beats the market. Any alpha discovered is a bonus; the primary deliverable is a working bot and the understanding that comes from shipping it.

## Core Value

**One thing that must work:** a running Alpaca paper-trading bot that places real sandbox orders based on daily EOD signals, backed by an honest backtest explorer the owner (and friends/mentors) can open in a browser.

Everything else — fancier features, risk layers, LLM-powered news reading — is secondary to this core loop running end-to-end.

## Context

### Current state (as of 2026-10-06)

- Working CLI pipeline: `python main.py backtest --ticker AAPL` fetches via yfinance, trains a RandomForest, runs an **honest** out-of-sample backtest with per-trade transaction costs and a confidence threshold
- 6 passing pytest tests covering: features, train/test leakage, backtest costs, confidence threshold
- All work committed and pushed to GitHub main
- No UI, no broker connection, no persistence, no LLM integration yet

### Audience

- **Primary:** Bryan (owner, beginner coder building with Claude Code)
- **Secondary:** Friends and mentors Bryan wants to show the project to; they may run it on their own machine

### Timeline

- Target to a running paper-trading bot: **2–4 weeks**
- Session-level cadence: a few hours per working session with Claude Code

### Constraints

- Solo developer, beginner skill level (every feature must be understandable and extensible by Bryan with Claude's help)
- No budget for paid data feeds or SaaS infra; must stay free-tier or local (yfinance for data, Alpaca paper for broker, local Streamlit for UI)
- Code lives in a public GitHub repo; secrets must stay in `.env` and never commit

## Requirements

### Validated (from existing codebase)

- ✓ Fetch daily OHLCV price history for any US ticker via yfinance — `stock_ai/data/loader.py`
- ✓ Compute technical indicator features (1-day return, SMA 10/50, RSI 14) — `stock_ai/features/indicators.py`
- ✓ Train a RandomForest classifier on chronological 80/20 train/test split — `stock_ai/models/classifier.py`
- ✓ Honest out-of-sample backtest with configurable transaction cost — `stock_ai/backtest/engine.py`
- ✓ Confidence-threshold signal generation (go long only when `predict_proba > threshold`) — `stock_ai/strategy/signal.py`
- ✓ CLI with `fetch`, `train`, `backtest` subcommands — `main.py`
- ✓ pytest suite locking in critical invariants (no train/test leakage, costs reduce returns, threshold reduces trade frequency)

### Active (v1 — what the milestone must deliver)

The v1 milestone is **"paper-trading bot in a browser"**. Requirements are grouped by capability area; detailed REQ-IDs will be assigned in `REQUIREMENTS.md`.

**UI (Backtest Explorer):**
- [ ] Streamlit app launchable with `streamlit run app.py` opens on `localhost:8501`
- [ ] User can enter ticker(s), date range, cost (bps), and confidence threshold, then click "Run Backtest"
- [ ] Results page shows: test accuracy, out-of-sample return, buy-and-hold return, Sharpe ratio, trade count, price chart with buy/sell markers
- [ ] Clear "in-sample vs out-of-sample" separation preserved from CLI

**Multi-Ticker Universe:**
- [ ] Support training/backtesting across a configurable list of 20–50+ US liquid equities and ETFs
- [ ] Cross-sectional ranking: on each decision day, rank candidates and go long the top-N by model probability
- [ ] Universe is configurable (default list in config, overridable in UI)

**Jev Integration:**
- [ ] Jev client wrapper (API key via `.env`, feature vector → typed decision)
- [ ] Jev-based signal mode selectable alongside the RandomForest baseline
- [ ] Clear comparison in the backtest explorer: RandomForest vs Jev results side-by-side

**Alpaca Paper Trading:**
- [ ] Alpaca client wrapper (API key via `.env`, paper endpoint)
- [ ] "Place paper orders for today's signals" action — generates signals from latest data, submits orders to Alpaca paper account
- [ ] "View paper account" page showing positions, cash, equity, recent orders

**Reliability + Honesty:**
- [ ] All new code has pytest coverage for its critical invariant
- [ ] README updated to reflect new usage (CLI + Streamlit)
- [ ] `.env.example` lists required keys with instructions
- [ ] Secrets never committed; `.gitignore` audited

### Deferred (v2)

- Walk-forward backtesting with rolling retraining (research called this out as the single highest-value measurement improvement; worth doing but after v1 ships)
- Model persistence (save/load trained models via joblib) so backtests don't retrain every run
- News/filings sentiment via FinGPT or similar LLM as an added feature
- Bootstrap confidence intervals on Sharpe
- Transaction cost modeling with per-ticker spreads (vs flat bps today)
- Risk management layer: volatility-targeted position sizing, max drawdown halts, portfolio-level caps

### Out of Scope

- **Live trading with real money** — not until v3+. Research is explicit: a strategy earns real money only after months of paper trading matching backtest Sharpe within confidence intervals. This is a learning project, not a live trading product.
- **Intraday trading** — strictly end-of-day decisions; no streaming data, no sub-daily bars
- **Multi-user / SaaS** — single-user local tool; no auth, no accounts, no cloud deployment
- **Options, futures, crypto, FX** — US equities and ETFs only
- **High-frequency / market-making** — Jev is capable of this but out of scope here
- **Mobile apps** — browser-based Streamlit only

## Key Decisions

| Decision | Rationale | Status |
|---|---|---|
| **Target: paper-trading bot in 2–4 weeks** | Owner wants something showable to mentors soon; keeps scope honest | Locked |
| **Audience: self + friends/mentors** | No multi-user complexity; local-run is fine | Locked |
| **Universe: 50+ US liquid equities** | Research called out cross-sectional strategies as more tractable than single-ticker; realistic path to a working bot | Locked |
| **Cadence: daily EOD** | Simplest realistic cadence; matches existing backtest; avoids streaming-data complexity | Locked |
| **AI model: Jev (TypeSafe AI, 2026)** | Owner wants to learn the tool. Explicitly experimental — research flagged Jev as unproven for this use case. Keep classical RandomForest as fallback/baseline for honest comparison. | Locked (with risk flag) |
| **Broker: Alpaca paper** | Free, $0 minimum, best Python SDK and docs for US retail bots per research | Locked |
| **UI: Streamlit backtest explorer** | Fastest path to a browser dashboard a beginner can own and extend; no HTML/JS skills required | Locked |
| **No risk layer in v1** | Owner chose speed over rigor for the first milestone. Risk layer deferred to v2 — explicitly a known gap. | Locked (with risk flag) |
| **Stack additions (planned):** Streamlit, Alpaca-py, Jev client, Plotly | Minimal set to deliver v1 goals; no framework-of-the-month churn | Pending |

## Risks

1. **Jev may not deliver useful signals for daily-EOD US-equity direction prediction.** Research flagged it as marketed for HFT/market-making; unproven for this task. Mitigation: keep RandomForest baseline wired up so the backtest explorer shows both; if Jev underperforms, pivot to using it as a feature-selection layer rather than the primary classifier.
2. **No risk layer in v1 means a buggy Jev integration could place many wrong-sized paper orders.** Paper account can't lose real money, but it can look like the bot is "working" when it's actually spraying noise. Mitigation: hard-code a per-order position cap in v1 even without a full risk framework; add verbose logging of every order rationale.
3. **2–4 week timeline is aggressive given scope (UI + multi-ticker + Jev + Alpaca).** Mitigation: ship incrementally — Streamlit UI first, then multi-ticker on existing RandomForest, then Alpaca hookup, then Jev last. Each layer is independently useful if the next one isn't ready yet.
4. **yfinance is the sole data source** and has no SLA. If it breaks mid-project, the whole pipeline stops. Mitigation: Alpaca market data is available on the free paper tier and could be a drop-in replacement; swap is noted as a cheap option if yfinance degrades.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-10-06 after initialization*

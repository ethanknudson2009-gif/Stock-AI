# Stock-AI — Project Context

**One-liner:** A Jev-powered automated stock-trading bot that paper-trades a broad
universe of US equities on a daily (EOD) cadence, backed by a browser-based
backtest explorer so every signal can be inspected before any paper order is placed.

**Primary goal:** Learning algorithmic trading, AI integration, and real-world system
plumbing by shipping something that actually runs — not beating the market. Any alpha
is a bonus; the deliverable is a working bot + the understanding from shipping it.

**Core value (the one thing that must work):** a running Alpaca paper-trading bot that
places real sandbox orders from daily EOD signals, backed by an honest backtest explorer.

## Current state (2026-10-13)
- Phases A–D of 8 shipped (see `.planning/ROADMAP.md`). 28 tests passing.
- A: `SignalBackend` Protocol · B: `.env` settings + default universe ·
  C: Streamlit single-ticker explorer · D: multi-ticker cross-sectional + portfolio Sharpe.
- Next: E (Broker Protocol + FakeBroker) → F (Alpaca paper) → G (EOD bot loop) → H (Jev).

## Honest caveat
The RandomForest model has no demonstrated edge yet (AAPL OOS ~45.6% accuracy,
underperforms buy & hold). The pipeline is sound; the signal is not — improve
features/labels before Phase G puts it in front of a broker.

## Locked decisions
- Universe: 20–50 large-cap US equities (see `stock_ai/config/universe.py`).
- Cadence: daily EOD · Broker: Alpaca paper · UI: Streamlit · Charts: Plotly.
- Secrets: `.env` + `python-dotenv` ONLY — never `st.secrets`.
- No risk layer in v1 (hard caps only).

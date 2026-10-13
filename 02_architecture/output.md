# 02 · Architecture — Output

## Package layout (pipeline-stage mirrored)
`stock_ai/data` → `features` → `models` (+ `config`) → `strategy` → `backtest`.
Entry points: `main.py` (CLI), `app.py` (Streamlit), future `bot.py` (EOD loop).

## Load-bearing abstractions
- **`SignalBackend` Protocol** (`stock_ai/models/base.py`) — every model conforms; no
  `isinstance` branching downstream. Lets RandomForest and Jev be interchangeable.
- **Broker Protocol** (Phase E) — `FakeBroker` for tests, `AlpacaPaperBroker` (Phase F)
  behind the same interface; `bot.py` never imports a concrete broker.

## Dependency rule
One-way only: `app`/`bot`/`main` → `stock_ai`. `stock_ai/` stays Streamlit-free and
broker-SDK-free except inside the adapter module.

## Core-loop data flow
`fetch_price_history → add_features → backend.predict_proba_up → generate_signals /
ranker.top_n → (backtest) run_backtest / run_multi_backtest  OR  (live) broker.submit`.

## Constraints
Positions shifted 1 day (no lookahead) · canonical trading-day calendar for multi-ticker
· `.env` + `load_dotenv()` once per entry point · US/Eastern for the bot clock (Phase G).

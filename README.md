# Stock-AI

An AI-driven stock trading system: pulls market data, trains a model to
generate trade signals, and backtests the strategy before any live/paper
trading.

## Project layout

```
app.py, views/   # Streamlit app: Home, Single Ticker, Portfolio, News Radar, My Trades, Paper Trade, About
ui/, ui_common.py  # theme + components; cached data helpers and charts
stock_ai/
  data/        # prices (yfinance), Alpaca news, Claude/word-list news sentiment
  features/    # indicators, regime and cross-sectional rank features
  models/      # classifier (walk-forward, purge gap), evaluation, 30-ticker harness
  strategy/    # baselines (buy & hold, SMA, momentum), ranking, vol-target sizing
  backtest/    # single- and multi-ticker engines
  execution/   # Alpaca paper broker, FakeBroker, risk rules, signal log
bot.py         # plans/submits paper orders (DRY_RUN, caps, KILL_SWITCH, risk rules)
main.py        # CLI: fetch / train / backtest
scripts/       # run_harness.py, daily_job.py (+ launchd installer), news backtest, screenshots
tests/         # unit tests
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add API keys if using a paid data/broker provider
```

## Usage

```bash
python main.py fetch --ticker AAPL --start 2015-01-01
python main.py train --ticker AAPL
python main.py backtest --ticker AAPL                    # default: 10 bps per trade
python main.py backtest --ticker AAPL --cost-bps 0       # zero-cost (optimistic)
python main.py backtest --ticker AAPL --threshold 0.55   # only trade high-conviction signals
```

## Secrets

API keys live in **one file only: `.env`** (gitignored). Copy `.env.example`
to `.env` and uncomment the keys you need — every key is optional, and the
CLI backtest needs none. Do not use `.streamlit/secrets.toml`. Code reads
keys through `stock_ai.config.load_settings()`, whose printed form masks
each key to its last 4 characters.

## Universe

The default multi-ticker universe is `DEFAULT_UNIVERSE` in
`stock_ai/config/universe.py` (30 large-cap US stocks). It is a *current*
snapshot, so historical backtests over it are **survivorship-biased** —
companies that failed or were delisted are missing.

## Run it

```bash
streamlit run app.py                         # the app at http://localhost:8501
PYTHONPATH=. python scripts/run_harness.py   # model-vs-baseline harness over 30 tickers (needs data/cache/raw.pkl)
python scripts/install_daily_job.py          # schedule the after-close paper-trading job (macOS launchd)
python scripts/install_daily_job.py --uninstall
scripts/go_live.sh                           # public temporary URL via Cloudflare tunnel, password-gated (--stop to close)
touch KILL_SWITCH                            # halt all order submission
python -m pytest -q
```

Keys in `.env`: `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` (paper only), optional `ANTHROPIC_API_KEY` for Claude-scored news.

## Status

Working end to end: purged walk-forward backtests with baselines, bootstrap Sharpe ranges and a cost-sensitivity
view; a minimum-edge rule ("No edge" instead of Buy); portfolio backtests vs equal-weight/SPY/momentum; Alpaca paper
trading with risk rules and a daily scheduled job; live news with a graded pick log; My Trades mirroring the paper account.

**The model has no reliable edge.** Across 30 stocks it roughly tracks buy & hold, and a shuffled-label control scores the
same Sharpe. News tone (word list) also showed no predictive power over two years. See `CHANGELOG.md` for the numbers
and what did not help. This is a learning and research tool; paper trading only.

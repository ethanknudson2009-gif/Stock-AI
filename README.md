# Stock-AI

An AI-driven stock trading system: pulls market data, trains a model to
generate trade signals, and backtests the strategy before any live/paper
trading.

## Project layout

```
stock_ai/
  data/        # data fetching & caching (price history, fundamentals)
  features/    # feature engineering (indicators, labels)
  models/      # model training/inference
  strategy/    # signal -> position sizing / trade decisions
  backtest/    # backtesting engine + performance metrics
main.py        # CLI entry point
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

## Status

Early scaffold — data pipeline, model, and backtester are functional but
minimal. `backtest` reports **out-of-sample** results (chronological
train/test split; signals generated only on held-out data) alongside the
in-sample numbers so the overfitting gap is visible, and applies a
configurable per-trade cost (default 10 bps for commission + slippage) so
numbers reflect something closer to live-trading friction. Still missing
for anything beyond a toy: walk-forward retraining, persisted model
artifacts, and better features/labels.

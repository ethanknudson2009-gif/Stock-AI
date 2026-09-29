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
python main.py backtest --ticker AAPL
```

## Status

Early scaffold — data pipeline, model, and backtester are functional but
minimal. **Known limitation:** `backtest` currently generates signals
using the model over the full dataset it was trained on, so results are
mostly in-sample and will look unrealistically good. Next step: score
only on the held-out test split (or walk-forward) before trusting any
backtest numbers.

"""About / help / glossary page."""

import streamlit as st

from ui.components import page_head

page_head("About", "What this is, how it works, and the honest caveats.", eyebrow="Docs")

st.subheader("What it does")
st.markdown("""
Stock AI Analyzer trains a model on a stock's past prices and tests a simple
**long/flat** strategy: when the model thinks the stock will rise, it holds; otherwise
it stays in cash. It then compares that strategy to just **buying and holding**.

Around that core sit **News Radar** (fresh headlines scored for tone), **My Trades** (your Alpaca paper account
mirrored here), and a **daily job** that logs signals, places paper orders for the top-ranked stocks after the
close, and grades its own past calls.
""")

st.subheader("How to read the results")
st.markdown("""
- **Out-of-sample (honest):** performance on data the model never trained on. *This is the number that matters.*
- **In-sample:** performance on the training data — always flattering, never trust it alone.
- **Strategy vs. Buy & hold:** beating buy & hold is hard; most of the time, holding wins.
- **Sharpe:** return per unit of risk (higher is better; ~1 is decent).
- **Max drawdown:** the worst peak-to-trough drop — how much pain you'd have felt.
""")

st.subheader("How results are tested")
st.markdown("""
- **Walk-forward:** the model is retrained on an expanding window and only ever predicts days it hasn't seen —
  the way a real bot would run.
- **Purge gap:** labels look 5 trading days ahead, so the last 5 rows before each test window are left out of
  training. Otherwise the model would get a peek at the test period.
- **Calibration:** the newest slice of each training window tunes the probabilities, so "60%" means roughly 60%.
- **Baselines:** every result sits next to buy & hold, a 50/200-day moving-average crossover, and (for portfolios)
  6-month momentum. If the model can't beat those, it isn't adding value.
- **The model:** a heavily regularized logistic regression (we compared it against a random forest, gradient
  boosting, other feature sets, an excess-return target, volatility sizing and rank features across 30 stocks;
  none beat buy & hold, so we kept the simplest and fastest).
- **Minimum-edge rule:** the benchmark is "always quote the stock's up-frequency from its training years". If the
  model's out-of-sample Brier score doesn't beat that *with statistical confidence* (a 20-day block bootstrap, 95%
  one-sided), the app says **"No edge"** instead of Buy or Sell. A tiny win that could be luck doesn't count.
- **Fills:** the backtest assumes you trade at the close that produced the signal. The live bot orders after the
  close and gets the next open, so real results will differ.
- **Robustness:** Sharpe ratios come with a 95% block-bootstrap range, and a cost-sensitivity chart shows how
  fragile the result is as trading costs rise.
- **Features:** multi-horizon returns, trend ratios, volatility (and its regime), RSI, volume surprise, drawdown, the stock's 200-day
  trend, and the market's (SPY) 200-day regime.
""")

st.subheader("Honest caveats")
st.markdown("""
- Predicting stocks is genuinely hard. The model has **no reliable edge** across all stocks — this is an *educational* tool, not a money machine.
- News tone is **unproven**: on two years of history the simple word-list score had no predictive power for
  next-week returns. Claude-scored news is untested; the live pick log will show whether it works.
- Backtests use today's list of stocks, so they're **survivorship-biased** (failed companies are missing) and look better than reality.
- **Not financial advice.** Paper trading only; real money is never touched.
""")

st.subheader("Safety")
st.markdown("""
- **DRY_RUN** is the master switch for every path (app, CLI and the daily job). While it is on, orders are logged and
  never sent; set `DRY_RUN=false` in `.env` to let the bot place **paper** orders (fake money, Alpaca's sandbox; the
  adapter refuses any non-paper endpoint).
- A **KILL_SWITCH** file halts all order submission instantly.
- **Sizing:** the bot aims to have about 75% of account equity invested, split across the names it buys, with no
  position above 20% of equity. It uses the cash it really has, never Alpaca's margin "buying power".
- **Hard caps** limit dollars per buy order ($25,000) and orders per day (20, counted across the whole day).
- **Risk rules:** at most 2 holdings per sector, a 10% per-position stop-loss (no re-buy for 7 days), and no new buys
  if the account is down 3% on the day. These are checked once a day, after the close, not during the session.
  The bot only manages its own 30-stock universe and never touches your manual holdings.
- **The bot only buys names with a reliable edge** (see the rule above), uses the same model the app evaluates,
  and refuses to trade at all if too many tickers can't be scored. A ticker with missing data is held, never sold blind.
- **Login:** the app listens only on this computer; anyone arriving through the tunnel or the local network must enter
  the password, and repeated wrong guesses lock everyone out for five minutes.
""")

with st.expander("Glossary"):
    st.markdown("""
- **Ticker** — a stock's symbol (AAPL = Apple).
- **Out-of-sample** — tested on unseen data; the honest measure.
- **Top-N** — hold the N highest-ranked stocks, rebalanced daily.
- **bps** — basis points; 10 bps = 0.1% cost per trade.
- **Brier score** — how far probabilities are from what happened (lower is better; the base-rate predictor is the bar).
- **IC (information coefficient)** — correlation between a score and later returns; ~0 means no predictive power.
- **Paper trading** — practice trading with fake money on a real broker sandbox.
""")

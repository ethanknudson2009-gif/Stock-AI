"""About / help / glossary page."""

import streamlit as st

from ui.components import page_head

page_head("About", "What this is, how it works, and the honest caveats.", eyebrow="Docs")

st.subheader("What it does")
st.markdown("""
Stock AI Analyzer trains a model on a stock's past prices and tests a simple
**long/flat** strategy: when the model thinks the stock will rise, it holds; otherwise
it stays in cash. It then compares that strategy to just **buying and holding**.
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
- **Features:** multi-horizon returns, trend ratios, volatility, RSI, volume surprise, the stock's 200-day trend,
  and the market's (SPY) 200-day regime.
""")

st.subheader("Honest caveats")
st.markdown("""
- Predicting stocks is genuinely hard. The model has **no reliable edge** across all stocks — this is an *educational* tool, not a money machine.
- Backtests use today's list of stocks, so they're **survivorship-biased** (failed companies are missing) and look better than reality.
- **Not financial advice.** Paper trading only; real money is never touched.
""")

st.subheader("Safety")
st.markdown("""
- **DRY_RUN** is on by default — orders are logged, never sent.
- A **KILL_SWITCH** file halts all trading instantly.
- **Hard caps** limit dollars per order and orders per day.
""")

with st.expander("Glossary"):
    st.markdown("""
- **Ticker** — a stock's symbol (AAPL = Apple).
- **Out-of-sample** — tested on unseen data; the honest measure.
- **Top-N** — hold the N highest-ranked stocks, rebalanced daily.
- **bps** — basis points; 10 bps = 0.1% cost per trade.
- **Paper trading** — practice trading with fake money on a real broker sandbox.
""")

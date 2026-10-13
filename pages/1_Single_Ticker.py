"""Single-ticker backtest page."""

import streamlit as st

from stock_ai.backtest.engine import run_backtest
from stock_ai.strategy.signal import generate_signals
from ui_common import SETTINGS, candle_chart, equity_chart, eyebrow, hero, inject_css, metrics_row, train

st.set_page_config(page_title="Single Ticker · Stock AI", page_icon="📈", layout="wide")
inject_css()
hero('📈 Single <span class="accent">Ticker</span>',
     "Backtest one stock. Honest out-of-sample results up top; overfitting-prone training numbers below.")

with st.sidebar:
    st.header("Settings")
    with st.form("single"):
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        start = st.text_input("Start date (YYYY-MM-DD)", value="2015-01-01")
        end = st.text_input("End date (YYYY-MM-DD)", value="2026-10-12")
        cost_bps = st.slider("Cost per trade (bps)", 0.0, 50.0, 10.0, 1.0)
        threshold = st.slider("Confidence threshold", 0.50, 0.70, 0.50, 0.01)
        submitted = st.form_submit_button("Run Backtest", width="stretch")

if not submitted:
    st.info("Enter a ticker in the sidebar and click **Run Backtest**.")
    st.stop()

try:
    with st.spinner(f"Fetching {ticker} and training…"):
        backend, accuracy, train_df, test_df = train(ticker, start, end)
        oos_positions = generate_signals(backend, test_df, threshold=threshold)
        oos = run_backtest(test_df, oos_positions, cost_bps=cost_bps)
        is_positions = generate_signals(backend, train_df, threshold=threshold)
        is_results = run_backtest(train_df, is_positions, cost_bps=cost_bps)
except Exception as exc:  # noqa: BLE001
    st.error(SETTINGS.scrub(f"Backtest failed: {type(exc).__name__}: {exc}"))
    st.stop()

st.subheader(f"✅ {ticker} — Out-of-sample (honest)")
st.caption(f"{test_df.index[0].date()} → {test_df.index[-1].date()} — held-out data the model never trained on.")
metrics_row(oos, accuracy)

delta = oos["total_return"] - oos["buy_hold_return"]
(st.success if delta >= 0 else st.warning)(
    f"Strategy {'beat' if delta >= 0 else 'trailed'} buy & hold by {abs(delta):.1%} out-of-sample."
)
left, right = st.columns([3, 2])
with left:
    eyebrow("Chart · Price action")
    st.plotly_chart(candle_chart(test_df, oos_positions), width="stretch")
with right:
    eyebrow("Chart · Equity curve")
    st.plotly_chart(equity_chart(oos["cumulative_returns"]), width="stretch")

with st.expander("⚠️ In-sample (training data — overfitting-prone, not a real result)"):
    st.caption(f"{train_df.index[0].date()} → {train_df.index[-1].date()} — the model saw this data, so it flatters.")
    metrics_row(is_results)

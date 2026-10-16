"""Single-ticker backtest page."""

import streamlit as st

from stock_ai.backtest.engine import run_backtest
from stock_ai.strategy.signal import generate_signals
from ui.components import page_head, section, stat_grid, tone, verdict
from ui_common import SETTINGS, candle_chart, equity_chart, train


def _stats(res, accuracy=None):
    stat_grid([
        ("Accuracy", f"{accuracy:.1%}" if accuracy is not None else "—", "accent"),
        ("Strategy return", f"{res['total_return']:+.1%}", tone(res["total_return"])),
        ("Buy & hold", f"{res['buy_hold_return']:+.1%}", ""),
        ("Sharpe", f"{res['sharpe_ratio']:.2f}", tone(res["sharpe_ratio"])),
        ("Max drawdown", f"{res['max_drawdown']:.1%}", "down"),
    ])
    st.caption(f"{res['n_trades']} trades · {res['cost_bps']:.0f} bps per trade")


page_head("Single Ticker", "Backtest one stock. Honest out-of-sample results first; training-period numbers below.", eyebrow="Backtest")

with st.form("single"):
    c = st.columns([1.2, 1, 1, 1.3, 1.3])
    ticker = c[0].text_input("Ticker", value="AAPL").strip().upper()
    start = c[1].text_input("Start (YYYY-MM-DD)", value="2015-01-01")
    end = c[2].text_input("End (YYYY-MM-DD)", value="2026-10-12")
    cost_bps = c[3].slider("Cost per trade (bps)", 0.0, 50.0, 10.0, 1.0)
    threshold = c[4].slider("Confidence threshold", 0.50, 0.70, 0.50, 0.01)
    submitted = st.form_submit_button("Run backtest", icon=":material/play_arrow:")

if not submitted:
    st.info("Pick a ticker and click **Run backtest**. Works for any US-listed stock.")
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

section(f"{ticker} · out-of-sample", f"{test_df.index[0].date()} → {test_df.index[-1].date()}")
_stats(oos, accuracy)

delta = oos["total_return"] - oos["buy_hold_return"]
verdict(f"Strategy {'beat' if delta >= 0 else 'trailed'} buy & hold by {abs(delta):.1%} on data the model never saw.",
        delta >= 0)

left, right = st.columns([3, 2], gap="medium")
with left:
    section("Price action", "last ~260 sessions")
    st.plotly_chart(candle_chart(test_df, oos_positions), width="stretch", theme=None)
with right:
    section("Equity curve", "growth of $1")
    st.plotly_chart(equity_chart(oos["cumulative_returns"]), width="stretch", theme=None)

with st.expander("In-sample results (training data — overfitting-prone)", icon=":material/warning:"):
    st.caption(f"{train_df.index[0].date()} → {train_df.index[-1].date()} — the model saw this data, so these numbers flatter it.")
    _stats(is_results)

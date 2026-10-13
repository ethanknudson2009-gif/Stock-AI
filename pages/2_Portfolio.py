"""Multi-ticker cross-sectional portfolio page."""

import streamlit as st

from stock_ai.config import DEFAULT_UNIVERSE
from ui_common import SETTINGS, equity_chart, hero, inject_css, portfolio_tiles, run_universe

st.set_page_config(page_title="Portfolio · Stock AI", page_icon="📊", layout="wide")
inject_css()
hero('📊 <span class="accent">Portfolio</span>',
     "Rank a universe of stocks each day and hold the top N. Honest portfolio Sharpe on the combined return series.")

with st.sidebar:
    st.header("Settings")
    with st.form("multi"):
        tickers_raw = st.text_area(
            "Tickers (comma-separated — blank = Default Universe)", value="",
            help=f"Default Universe = {len(DEFAULT_UNIVERSE)} large-cap US stocks.")
        top_n = st.slider("Top-N held", 1, 15, 5, 1)
        start = st.text_input("Start date (YYYY-MM-DD)", value="2015-01-01")
        end = st.text_input("End date (YYYY-MM-DD)", value="2026-10-12")
        cost_bps = st.slider("Cost per trade (bps)", 0.0, 50.0, 10.0, 1.0)
        submitted = st.form_submit_button("Run Backtest", width="stretch")

if not submitted:
    st.info("Set your universe in the sidebar and click **Run Backtest**.")
    st.stop()

tickers = tuple(t.strip().upper() for t in tickers_raw.replace("\n", ",").split(",") if t.strip()) \
    or tuple(DEFAULT_UNIVERSE)

try:
    with st.spinner(f"Fetching & training {len(tickers)} tickers…"):
        res, equity, skipped = run_universe(tickers, start, end, top_n, cost_bps)
except Exception as exc:  # noqa: BLE001
    st.error(SETTINGS.scrub(f"Backtest failed: {type(exc).__name__}: {exc}"))
    st.stop()

st.subheader("✅ Portfolio out-of-sample (honest)")
st.caption(f"Equal-weight top-{top_n}, daily rebalance, {res['n_days']} sessions. "
           f"Held ~{res['avg_positions']:.1f} names/day. Survivorship-biased: current snapshot.")
portfolio_tiles(res)
st.caption("Portfolio Sharpe (equal-weight top-N, daily rebalance) — computed on the combined daily return series.")
if skipped:
    st.warning(f"Skipped (no data): {', '.join(skipped)}")

delta = res["total_return"] - res["buy_hold_return"]
(st.success if delta >= 0 else st.warning)(
    f"Top-{top_n} {'beat' if delta >= 0 else 'trailed'} the equal-weight-all benchmark by {abs(delta):.1%}.")
st.plotly_chart(equity_chart(equity), width="stretch")

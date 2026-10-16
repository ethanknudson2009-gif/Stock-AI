"""Multi-ticker cross-sectional portfolio page."""

import streamlit as st

from stock_ai.config import DEFAULT_UNIVERSE
from ui.components import page_head, section, stat_grid, tone, verdict
from ui_common import SETTINGS, equity_chart, run_universe

page_head("Portfolio", "Rank a universe each day and hold the top N. Sharpe is computed on the combined portfolio return.", eyebrow="Universe")

with st.form("multi"):
    tickers_raw = st.text_area(
        "Tickers (comma-separated — leave blank for the Default Universe)", value="", height=68,
        help=f"Default Universe = {len(DEFAULT_UNIVERSE)} large-cap US stocks.")
    c = st.columns(4)
    top_n = c[0].slider("Top-N held", 1, 15, 5, 1)
    start = c[1].text_input("Start (YYYY-MM-DD)", value="2015-01-01")
    end = c[2].text_input("End (YYYY-MM-DD)", value="2026-10-12")
    cost_bps = c[3].slider("Cost per trade (bps)", 0.0, 50.0, 10.0, 1.0)
    submitted = st.form_submit_button("Run backtest", icon=":material/play_arrow:")

if not submitted:
    st.info("Set your universe and click **Run backtest**. A full Default Universe run takes a minute.")
    st.stop()

tickers = tuple(t.strip().upper() for t in tickers_raw.replace("\n", ",").split(",") if t.strip()) \
    or tuple(DEFAULT_UNIVERSE)

try:
    with st.spinner(f"Fetching & training {len(tickers)} tickers…"):
        res, equity, skipped = run_universe(tickers, start, end, top_n, cost_bps)
except Exception as exc:  # noqa: BLE001
    st.error(SETTINGS.scrub(f"Backtest failed: {type(exc).__name__}: {exc}"))
    st.stop()

section("Portfolio · out-of-sample", f"top-{top_n} · {res['n_days']} sessions · ~{res['avg_positions']:.1f} names/day")
stat_grid([
    ("Portfolio return", f"{res['total_return']:+.1%}", tone(res["total_return"])),
    ("Equal-weight all", f"{res['buy_hold_return']:+.1%}", ""),
    ("Portfolio Sharpe", f"{res['portfolio_sharpe']:.2f}", tone(res["portfolio_sharpe"])),
    ("Max drawdown", f"{res['max_drawdown']:.1%}", "down"),
])
st.caption("Equal-weight top-N, daily rebalance. Survivorship-biased: the universe is today's snapshot.")
if skipped:
    st.warning(f"Skipped (no data): {', '.join(skipped)}")

delta = res["total_return"] - res["buy_hold_return"]
verdict(f"Top-{top_n} {'beat' if delta >= 0 else 'trailed'} the equal-weight benchmark by {abs(delta):.1%}.", delta >= 0)

section("Equity curve", "growth of $1")
st.plotly_chart(equity_chart(equity), width="stretch", theme=None)

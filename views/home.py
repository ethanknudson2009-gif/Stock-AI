"""Home — market overview and entry points to each tool."""

import streamlit as st

from ui.components import hero, nav_card, section, ticker_grid
from ui_common import WATCHLIST, watchlist_as_of, watchlist_quotes

with st.spinner("Loading market data…"):
    quotes = watchlist_quotes()
    as_of = watchlist_as_of()

gainers = sum(1 for q in quotes if q["pct"] >= 0)
losers = len(quotes) - gainers
hero(
    "Markets,", "decoded", ".",
    "Honest, model-driven backtests and signals for any US stock — test an idea before you risk a dollar.",
    chips=[
        ("up", "Gainers", str(gainers)),
        ("down", "Losers", str(losers)),
        ("accent", "Updated", as_of),
    ] if quotes else None,
)

section("Market overview", f"{len(WATCHLIST)} large caps · daily change", eyebrow="Live market", center=True)
ticker_grid(quotes)

section("Analysis suite", "Four tools, one honest engine", eyebrow="The full picture", center=True)
row1 = st.columns(2, gap="medium")
row2 = st.columns(2, gap="medium")
with row1[0]:
    nav_card("single", "views/single_ticker.py", "candlestick_chart", "Single Ticker",
             "Backtest one stock with candlesticks and honest out-of-sample stats.")
with row1[1]:
    nav_card("portfolio", "views/portfolio.py", "donut_large", "Portfolio",
             "Rank a universe each day, hold the top N, see a true portfolio Sharpe.")
with row2[0]:
    nav_card("paper", "views/paper_trade.py", "receipt_long", "Paper Trade",
             "Preview today's orders, then confirm — safe by default with DRY_RUN.")
with row2[1]:
    nav_card("about", "views/about.py", "info", "About",
             "How it works, how to read results, and the honest caveats.")

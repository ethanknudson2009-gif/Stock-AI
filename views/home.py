"""Home — live market overview, ticker search, preset launches."""

import streamlit as st

from stock_ai.config import DEFAULT_UNIVERSE, PRESETS
from ui import theme
from ui.components import hero, nav_card, section, skeleton_grid, ticker_grid
from ui_common import fmt_stamp, latest_trading_day, now_et, valid_ticker, watchlist_quotes

TICKERS = tuple(DEFAULT_UNIVERSE[:8])
ss = st.session_state


def _refresh():
    watchlist_quotes.clear()


NOW = now_et()
hero(
    "Markets,", "decoded", ".",
    "Honest, model-driven backtests and signals for any US stock — test an idea before you risk a dollar.",
)

# ---- Live market overview ----
section("Market overview", f"{NOW:%A, %B %d, %Y · %-I:%M %p %Z}", eyebrow="Live market")
bar = st.columns([4, 1], vertical_alignment="center")

placeholder = st.empty()
with placeholder:
    st.markdown(skeleton_grid(8), unsafe_allow_html=True)
quotes, fetched_at = watchlist_quotes(TICKERS)
placeholder.empty()

gainers = sum(1 for q in quotes if q["pct"] >= 0)
losers = len(quotes) - gainers
bar[0].caption(
    f"Updated {fmt_stamp(fetched_at)} · {gainers} up / {losers} down · session {latest_trading_day(NOW):%b %d}"
    if quotes else "Market data unavailable — try Refresh."
)
bar[1].button("Refresh", icon=":material/refresh:", on_click=_refresh, width="stretch")

ticker_grid(quotes, theme_name=theme.current())

# ---- Ticker search ----
section("Analyze a ticker", "Any US-listed symbol — AAPL, MSFT, NVDA, TSLA…", eyebrow="Search")
with st.form("ticker_search", clear_on_submit=False):
    cols = st.columns([3, 1], vertical_alignment="bottom")
    q = cols[0].text_input("Ticker", placeholder="e.g. AAPL", label_visibility="collapsed", key="home_search")
    go = cols[1].form_submit_button("Analyze", icon=":material/arrow_forward:", width="stretch")
    if go:
        t = (q or "").strip().upper()
        if not valid_ticker(t):
            st.error("That doesn't look like a ticker. Try symbols like AAPL, MSFT, or BRK-B.")
        else:
            ss["preload_ticker"] = t
            st.switch_page("views/single_ticker.py")

# ---- Launchers ----
section("Analysis suite", "Six tools, one honest engine", eyebrow="The full picture")
row1 = st.columns(3, gap="medium")
row2 = st.columns(3, gap="medium")
with row1[0]:
    nav_card("single", "views/single_ticker.py", "candlestick_chart", "Single Ticker",
             "Backtest one stock with candlesticks and honest out-of-sample stats.")
with row1[1]:
    nav_card("portfolio", "views/portfolio.py", "donut_large", "Portfolio",
             "Rank a universe each day, hold the top N, see a true portfolio Sharpe.")
with row1[2]:
    nav_card("news", "views/news.py", "newspaper", "News Radar",
             "Fresh headlines scored for tone and ranked by ticker, with a live track record.")
with row2[0]:
    nav_card("paper", "views/paper_trade.py", "receipt_long", "Paper Trade",
             "Preview today's orders, then confirm — safe by default with DRY_RUN.")
with row2[1]:
    nav_card("trades", "views/my_trades.py", "account_balance_wallet", "My Trades",
             "Your Alpaca paper account mirrored here: orders, positions, P&L and account value.")
with row2[2]:
    nav_card("about", "views/about.py", "info", "About",
             "How it works, how to read results, and the honest caveats.")

# ---- Preset universes ----
section("Preset universes", "One click into Portfolio with a universe pre-selected", eyebrow="Shortcuts")
cols = st.columns(len(PRESETS))
for col, name in zip(cols, PRESETS):
    with col:
        with st.container(border=True, key=f"preset_{name}"):
            st.markdown(f"**{name}**")
            st.caption(f"{len(PRESETS[name])} tickers")
            if st.button(f"Open {name}", key=f"go_{name}", width="stretch"):
                ss["preload_preset"] = name
                st.switch_page("views/portfolio.py")

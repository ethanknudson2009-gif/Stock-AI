"""Home — live market overview, ticker search, preset launches."""

import json
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from stock_ai.config import DEFAULT_UNIVERSE, PRESETS
from ui import theme
from ui.components import hero, nav_card, section, skeleton_grid, stat_grid, ticker_grid, tone
from ui_common import (account_snapshot, fmt_stamp, latest_trading_day, news_for, now_et, valid_ticker,
                       watchlist_quotes)

STATE = Path(__file__).resolve().parent.parent / "logs" / "daily_state.json"

TICKERS = tuple(DEFAULT_UNIVERSE[:10])
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
    st.markdown(skeleton_grid(10), unsafe_allow_html=True)
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

# ---- Bot + news at a glance ----
g1, g2 = st.columns([1, 1.25], gap="large")
with g1:
    section("Your bot", "Alpaca paper account", eyebrow="At a glance")
    snap = account_snapshot()
    if snap is None:
        st.info("Connect Alpaca keys in .env to see your paper account here.")
    else:
        a, pos, od = snap["account"], snap["positions"], snap["orders"]
        waiting = sum(1 for o in od if o["status"] in ("accepted", "new", "pending_new", "held", "partially_filled"))
        try:
            last_run = json.loads(STATE.read_text()).get("last_done", "not yet")
        except (OSError, ValueError):
            last_run = "not yet"
        stat_grid([("Account value", f"${a['equity']:,.0f}", "accent"),
                   (f"Today ({a['day_pl_pct']:+.2%})", f"{a['day_pl']:+,.2f}", tone(a["day_pl"])),
                   ("Positions", f"{len(pos)}", ""), ("Orders waiting", f"{waiting}", ""),
                   ("Last daily run", last_run, "")])
        st.page_link("views/my_trades.py", label="Open My Trades", icon=":material/arrow_forward:")
with g2:
    section("In the news", "newest headlines across the 30-stock universe", eyebrow="Live news")
    try:
        feed = news_for(tuple(DEFAULT_UNIVERSE), 1, False)
        feed = feed[feed["symbols"].apply(len) <= 3].sort_values("time", ascending=False).head(6)
        for _, n in feed.iterrows():
            hrs = (pd.Timestamp.now(tz="UTC") - n["time"]).total_seconds() / 3600
            when = f"{hrs * 60:.0f}m ago" if hrs < 1 else f"{hrs:.0f}h ago"
            st.markdown(f'<div class="note"><span class="badge">{escape(", ".join(n["symbols"][:3]))}</span>&nbsp; '
                        f'<a href="{escape(n["url"] or "#")}" target="_blank" rel="noopener">{escape(n["headline"][:130] + ("…" if len(n["headline"]) > 130 else ""))}</a> '
                        f'<span style="opacity:.6">— {when}</span></div>', unsafe_allow_html=True)
        st.page_link("views/news.py", label="Open News Radar", icon=":material/arrow_forward:")
    except Exception:  # noqa: BLE001 — Home must still load without news/keys
        st.info("News is unavailable right now. Check the Alpaca keys in .env.")

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

"""Stock AI Analyzer — Home (cyberpunk market dashboard).

Run with: streamlit run app.py  (opens http://localhost:8501)
Streamlit auto-discovers the pages/ folder for the sidebar navigation.
"""

from datetime import datetime

import streamlit as st

from ui_common import (
    GOLD_SOFT, GREEN, MAGENTA, RED, TAN_DIM,
    eyebrow, hero, inject_css, market_cards, watchlist_quotes,
)

st.set_page_config(page_title="Stock AI Analyzer", page_icon="📈", layout="wide")
inject_css()

hero(
    'STOCK <span class="accent">//</span> AI  TERMINAL',
    f"Neural market terminal · {datetime.now():%A, %b %d · %H:%M}",
)

# --- Live market overview (real data) ---
eyebrow("Live · Market Pulse")
st.subheader("Market Overview")
with st.spinner("Pulling market data…"):
    quotes = watchlist_quotes()

if quotes:
    gainers = sum(1 for q in quotes if q["pct"] >= 0)
    avg = sum(q["pct"] for q in quotes) / len(quotes)
    top, bottom = quotes[0], quotes[-1]
    s = st.columns(4)
    s[0].metric("Watchlist", f"{len(quotes)} names")
    s[1].metric("Advancing", f"{gainers}/{len(quotes)}")
    s[2].metric("Top mover", f"{top['ticker']} {top['pct']:+.2f}%")
    s[3].metric("Avg change", f"{avg:+.2f}%")
market_cards(quotes)

st.divider()

# --- Launch tools ---
eyebrow("Run · Tools")
st.subheader("Analysis Suite")


def _card(col, tag, title, desc, page, label, icon):
    with col:
        with st.container(border=True):
            st.markdown(f'<span class="eyebrow">{tag}</span>', unsafe_allow_html=True)
            st.subheader(title)
            st.caption(desc)
            st.page_link(page, label=label, icon=icon)


r1c1, r1c2 = st.columns(2)
_card(r1c1, "Backtest · Single", "Single Ticker",
      "Backtest one stock with candlesticks, honest out-of-sample stats, and buy/sell signals.",
      "pages/1_Single_Ticker.py", "Launch Single Ticker", "📈")
_card(r1c2, "Backtest · Universe", "Portfolio",
      "Rank many stocks and hold the top N. Portfolio equity curve and honest Sharpe.",
      "pages/2_Portfolio.py", "Launch Portfolio", "📊")

r2c1, r2c2 = st.columns(2)
_card(r2c1, "Execute · Safe", "Paper Trade",
      "Preview today's intended orders, then confirm. Safe by default — nothing sent unless DRY_RUN is off.",
      "pages/3_Paper_Trade.py", "Launch Paper Trade", "🧾")
_card(r2c2, "Learn · Docs", "About",
      "What this is, how it works, honest caveats, and a plain-English glossary.",
      "pages/4_About.py", "Open About", "ℹ️")

st.divider()
st.markdown(
    f"<p style='color:{TAN_DIM}'>Runs on <b style='color:{GOLD_SOFT}'>any US-listed ticker</b> "
    f"Yahoo Finance covers. <span style='color:{MAGENTA}'>Educational tool — not financial advice.</span></p>",
    unsafe_allow_html=True,
)

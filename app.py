"""Stock AI Analyzer — Home.

Run with: streamlit run app.py  (opens http://localhost:8501)
Streamlit auto-discovers the pages/ folder for the sidebar navigation.
"""

import streamlit as st

from ui_common import GOLD_SOFT, TAN_DIM, hero, inject_css

st.set_page_config(page_title="Stock AI Analyzer", page_icon="📈", layout="wide")
inject_css()

hero(
    'Stock <span class="accent">AI</span> Analyzer',
    "A beginner-friendly tool to test stock strategies honestly — before risking anything.",
)

st.markdown(
    f"""
Welcome 👋 This app trains a model on a stock's history and shows, **honestly**,
how a simple buy/sell strategy would have performed — including the overfitting
gap most tools hide. Pick a page from the sidebar, or start here:
"""
)

c1, c2 = st.columns(2)
with c1:
    st.subheader("📈 Single Ticker")
    st.caption("Backtest one stock. See accuracy, return vs. buy & hold, Sharpe, and a buy/sell chart.")
    st.page_link("pages/1_Single_Ticker.py", label="Open Single Ticker", icon="📈")

    st.subheader("🧾 Paper Trade")
    st.caption("Preview today's intended orders and (optionally) submit them to a safe paper account.")
    st.page_link("pages/3_Paper_Trade.py", label="Open Paper Trade", icon="🧾")
with c2:
    st.subheader("📊 Portfolio")
    st.caption("Rank many stocks and hold the top N. See a portfolio equity curve and honest Sharpe.")
    st.page_link("pages/2_Portfolio.py", label="Open Portfolio", icon="📊")

    st.subheader("ℹ️ About")
    st.caption("What this is, how it works, the honest caveats, and a plain-English glossary.")
    st.page_link("pages/4_About.py", label="Open About", icon="ℹ️")

st.divider()
st.markdown(
    f"<p style='color:{TAN_DIM}'>Works for <b style='color:{GOLD_SOFT}'>any US-listed stock</b> "
    "Yahoo Finance covers — just type a ticker (AAPL, MSFT, NVDA, TSLA, …). "
    "This is an educational tool, not financial advice.</p>",
    unsafe_allow_html=True,
)

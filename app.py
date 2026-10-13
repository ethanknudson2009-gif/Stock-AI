"""Stock AI Analyzer — Home (cyberpunk dashboard).

Run with: streamlit run app.py  (opens http://localhost:8501)
Streamlit auto-discovers the pages/ folder for the sidebar navigation.
"""

import streamlit as st

from ui_common import GOLD_SOFT, MAGENTA, TAN_DIM, hero, inject_css

st.set_page_config(page_title="Stock AI Analyzer", page_icon="📈", layout="wide")
inject_css()

hero(
    'STOCK <span class="accent">//</span> AI  ANALYZER',
    "Neural signal terminal — test strategies honestly before you risk anything.",
)


def _card(col, eyebrow, title, desc, page, label, icon):
    with col:
        with st.container(border=True):
            st.markdown(f'<span class="eyebrow">{eyebrow}</span>', unsafe_allow_html=True)
            st.subheader(title)
            st.caption(desc)
            st.page_link(page, label=label, icon=icon)


r1c1, r1c2 = st.columns(2)
_card(r1c1, "Run · Backtest", "Single Ticker",
      "Backtest one stock. Accuracy, return vs. buy & hold, Sharpe, and a neon buy/sell chart.",
      "pages/1_Single_Ticker.py", "Launch Single Ticker", "📈")
_card(r1c2, "Run · Universe", "Portfolio",
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
    f"Yahoo Finance covers (AAPL, MSFT, NVDA, TSLA, …). "
    f"<span style='color:{MAGENTA}'>Educational tool — not financial advice.</span></p>",
    unsafe_allow_html=True,
)

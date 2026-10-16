"""Stock AI Analyzer — app entry point and router.

Run with: streamlit run app.py  (opens http://localhost:8501)
Owns page config, top navigation, the theme toggle, theme injection and the
footer, so every page gets them. Page content lives in views/.
"""

import streamlit as st

from ui import theme
from ui.components import footer

st.set_page_config(page_title="Stock AI", page_icon=":material/monitoring:", layout="wide")

theme.init()
with st.container(key="theme_toggle"):
    st.toggle(":material/light_mode:", key="light_mode")
theme.apply()
st.logo(theme.logo_path(), size="large")

pages = [
    st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("views/single_ticker.py", title="Single Ticker", icon=":material/candlestick_chart:"),
    st.Page("views/portfolio.py", title="Portfolio", icon=":material/donut_large:"),
    st.Page("views/news.py", title="News Radar", icon=":material/newspaper:"),
    st.Page("views/my_trades.py", title="My Trades", icon=":material/account_balance_wallet:"),
    st.Page("views/paper_trade.py", title="Paper Trade", icon=":material/receipt_long:"),
    st.Page("views/about.py", title="About", icon=":material/info:"),
]
footer()  # placed first in the DOM, pinned to the bottom with CSS order
st.navigation(pages, position="top").run()

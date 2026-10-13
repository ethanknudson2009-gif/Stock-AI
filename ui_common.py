"""Shared UI theme, cached data helpers, and chart/metric builders for all pages.

One place for the brand palette and the Streamlit caches so every page looks and
behaves identically. Kept import-light: no trading happens at import time.
"""

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from stock_ai.backtest.multi_engine import backtest_universe
from stock_ai.config import load_settings
from stock_ai.data.loader import fetch_price_history
from stock_ai.execution import FakeBroker
from stock_ai.features.indicators import add_features
from stock_ai.models.classifier import train_model
from stock_ai.models.rf_backend import RandomForestBackend

load_dotenv()
SETTINGS = load_settings()

# --- thinkorswim-style terminal palette: gold / green / tan on charcoal ---
GOLD = "#D9A441"        # accent / highlighted values
GOLD_SOFT = "#E6BE63"
GREEN = "#2FBF71"       # up / buy
GREEN_DEEP = "#15171B"  # panel
CANVAS = "#0B0C0E"      # terminal background
PANEL = "#15171B"
BORDER = "#2A2D33"      # thin panel borders
TAN = "#D7D2C4"         # primary text
TAN_DIM = "#8A8577"     # dim uppercase labels
RED = "#E24A3B"         # down / sell


def inject_css() -> None:
    """thinkorswim-style terminal styling shared by every page."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');
        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; font-size: 14px; }}
        .block-container {{ padding-top: 1.1rem; max-width: 1240px; }}

        /* Section headers: uppercase terminal style */
        h1, h2, h3 {{
            font-family: 'Roboto Mono', monospace !important; color: {TAN} !important;
            text-transform: uppercase; letter-spacing: 1px; font-weight: 700 !important;
        }}
        h2, h3 {{ font-size: 1.0rem !important; border-left: 3px solid {GOLD};
                  padding-left: .55rem; margin: 1rem 0 .4rem !important; }}

        /* Slim top bar instead of a big banner */
        .tos-bar {{
            display:flex; align-items:center; justify-content:space-between;
            background: {PANEL}; border: 1px solid {BORDER}; border-top: 2px solid {GOLD};
            border-radius: 6px; padding: .6rem .9rem; margin-bottom: .9rem;
        }}
        .tos-bar .title {{ font-family:'Roboto Mono',monospace; font-weight:700;
            font-size:1.15rem; letter-spacing:1px; text-transform:uppercase; color:{TAN}; }}
        .tos-bar .title .accent {{ color:{GOLD}; }}
        .tos-bar .sub {{ color:{TAN_DIM}; font-size:.78rem; font-family:'Roboto Mono',monospace;
            text-align:right; max-width:55%; }}

        /* Stat tiles (thinkorswim quote cells) */
        .tos-tiles {{ display:flex; flex-wrap:wrap; gap:8px; margin:.3rem 0 .6rem; }}
        .tos-tile {{ flex:1 1 150px; background:{PANEL}; border:1px solid {BORDER};
            border-radius:5px; padding:.55rem .7rem; }}
        .tos-tile .lbl {{ color:{TAN_DIM}; font-size:.66rem; text-transform:uppercase;
            letter-spacing:.8px; font-family:'Roboto Mono',monospace; }}
        .tos-tile .val {{ font-family:'Roboto Mono',monospace; font-weight:700;
            font-size:1.35rem; margin-top:.15rem; }}

        /* Native metrics fallback → same terminal look */
        [data-testid="stMetric"] {{ background:{PANEL}; border:1px solid {BORDER};
            border-radius:5px; padding:.55rem .7rem; }}
        [data-testid="stMetricLabel"] p {{ color:{TAN_DIM} !important; font-size:.66rem !important;
            text-transform:uppercase; letter-spacing:.8px; }}
        [data-testid="stMetricValue"] {{ color:{GOLD} !important; font-family:'Roboto Mono',monospace !important;
            font-weight:700 !important; }}

        /* Buttons: flat terminal */
        .stButton > button, .stFormSubmitButton > button {{
            background:{GOLD}; color:#141008; font-weight:700; border:none; border-radius:4px;
            font-family:'Roboto Mono',monospace; text-transform:uppercase; letter-spacing:.5px;
            padding:.45rem .9rem; }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{ filter:brightness(1.1); color:#141008; }}

        /* Sidebar */
        [data-testid="stSidebar"] {{ background:{PANEL}; border-right:1px solid {BORDER}; }}
        [data-testid="stSidebar"] .stForm {{ border:1px solid {BORDER}; border-radius:6px; }}
        [data-testid="stSidebarNav"] a span {{ color:{TAN} !important; font-family:'Roboto Mono',monospace; }}

        /* Inputs + dense tables */
        input, textarea, [data-baseweb="select"] > div {{ border-radius:4px !important;
            font-family:'Roboto Mono',monospace !important; }}
        [data-testid="stTable"] table {{ border:1px solid {BORDER}; font-family:'Roboto Mono',monospace;
            font-size:.82rem; }}
        [data-testid="stTable"] th {{ background:{CANVAS}; color:{TAN_DIM} !important;
            text-transform:uppercase; letter-spacing:.5px; }}
        [data-testid="stTable"] tr:nth-child(even) td {{ background:rgba(255,255,255,0.02); }}
        a {{ color:{GOLD_SOFT}; }}
        .stAlert {{ border-radius:5px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title_html: str, subtitle: str) -> None:
    """Render the slim terminal top bar (title may include <span class='accent'>)."""
    st.markdown(
        f'<div class="tos-bar"><div class="title">{title_html}</div>'
        f'<div class="sub">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def stat_tiles(items) -> None:
    """Render a row of terminal quote tiles. items: list of (label, value, tone).

    tone ∈ {"gold","up","down","neutral"} colors the value like a quote cell.
    """
    tone_color = {"gold": GOLD, "up": GREEN, "down": RED, "neutral": TAN}
    cells = "".join(
        f'<div class="tos-tile"><div class="lbl">{lbl}</div>'
        f'<div class="val" style="color:{tone_color.get(tone, TAN)}">{val}</div></div>'
        for lbl, val, tone in items
    )
    st.markdown(f'<div class="tos-tiles">{cells}</div>', unsafe_allow_html=True)


def _sign_tone(x: float) -> str:
    return "up" if x > 0 else ("down" if x < 0 else "neutral")


@st.cache_data(ttl=3600, show_spinner=False)
def load_prices(ticker: str, start: str, end: str):
    """Cached yfinance fetch + feature engineering, keyed by (ticker, start, end)."""
    return add_features(fetch_price_history(ticker, start, end))


@st.cache_resource(show_spinner=False)
def train(ticker: str, start: str, end: str):
    """Cached training. Returns (backend, accuracy, train_df, test_df)."""
    model, accuracy, train_df, test_df = train_model(load_prices(ticker, start, end))
    return RandomForestBackend.from_fitted(model), accuracy, train_df, test_df


@st.cache_data(ttl=3600, show_spinner=False)
def run_universe(tickers, start: str, end: str, top_n: int, cost_bps: float):
    """Cached multi-ticker cross-sectional backtest. Returns (results, equity, skipped)."""
    frames, skipped = {}, []
    for t in tickers:
        try:
            frames[t] = load_prices(t, start, end)
        except Exception:  # noqa: BLE001
            skipped.append(t)
    results, _proba, _returns = backtest_universe(
        frames, RandomForestBackend, top_n_count=top_n, cost_bps=cost_bps
    )
    return results, results["cumulative_returns"], skipped


def _style_fig(fig, yaxis_title: str):
    fig.update_layout(
        height=430, margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1.02, yanchor="bottom"),
        xaxis_title=None, yaxis_title=yaxis_title,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TAN),
    )
    fig.update_xaxes(gridcolor="rgba(231,220,195,0.08)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(231,220,195,0.08)", zeroline=False)


def price_chart(test_df, positions):
    """Close-price line with gold line and green buy / red sell markers."""
    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=test_df.index, y=test_df["Close"], mode="lines",
        name="Close", line=dict(color=GOLD, width=2)))
    changes = positions.diff().fillna(positions)
    buys = test_df.index[changes == 1]
    sells = test_df.index[changes == -1]
    fig.add_trace(go.Scattergl(
        x=buys, y=test_df.loc[buys, "Close"], mode="markers", name="Buy",
        marker=dict(symbol="triangle-up", size=11, color=GREEN, line=dict(width=1, color=TAN))))
    fig.add_trace(go.Scattergl(
        x=sells, y=test_df.loc[sells, "Close"], mode="markers", name="Sell",
        marker=dict(symbol="triangle-down", size=11, color=RED, line=dict(width=1, color=TAN))))
    _style_fig(fig, "Price ($)")
    return fig


def equity_chart(cumulative):
    """Portfolio equity curve (growth of $1)."""
    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=cumulative.index, y=cumulative, mode="lines",
        name="Portfolio", line=dict(color=GOLD, width=2)))
    _style_fig(fig, "Growth of $1")
    return fig


def metrics_row(res, accuracy=None):
    """Terminal quote tiles for a single-ticker backtest result dict."""
    stat_tiles([
        ("Accuracy", f"{accuracy:.1%}" if accuracy is not None else "—", "gold"),
        ("Strategy", f"{res['total_return']:+.1%}", _sign_tone(res["total_return"])),
        ("Buy & Hold", f"{res['buy_hold_return']:+.1%}", "neutral"),
        ("Sharpe", f"{res['sharpe_ratio']:.2f}", _sign_tone(res["sharpe_ratio"])),
        ("Max DD", f"{res['max_drawdown']:.1%}", "down"),
    ])
    st.caption(f"{res['n_trades']} trades @ {res['cost_bps']:.0f} bps")


def portfolio_tiles(res):
    """Terminal quote tiles for a multi-ticker portfolio result dict."""
    stat_tiles([
        ("Portfolio", f"{res['total_return']:+.1%}", _sign_tone(res["total_return"])),
        ("Equal-Wt All", f"{res['buy_hold_return']:+.1%}", "neutral"),
        ("Port Sharpe", f"{res['portfolio_sharpe']:.2f}", _sign_tone(res["portfolio_sharpe"])),
        ("Max DD", f"{res['max_drawdown']:.1%}", "down"),
    ])


def get_broker():
    """Return (broker, label): the real Alpaca paper broker, or a demo FakeBroker."""
    try:
        from stock_ai.execution.paper import AlpacaPaperBroker

        return AlpacaPaperBroker(), "Alpaca paper account"
    except Exception:  # noqa: BLE001
        return FakeBroker(), "FakeBroker (no Alpaca keys — demo only, empty positions)"

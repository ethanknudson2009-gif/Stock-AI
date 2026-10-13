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

# --- CYBERPUNK neon palette (names kept stable; values are neon) ---
GOLD = "#22E3FF"        # primary accent → neon cyan (chart line, highlights)
GOLD_SOFT = "#5EEBFF"
GREEN = "#2EF2A6"       # up / buy → neon green
GREEN_DEEP = "#0F1020"  # panel
CANVAS = "#08080F"      # deep space-black
PANEL = "#0F1020"
BORDER = "#242847"      # bluish neon border
TAN = "#E6F0FF"         # cool-white text
TAN_DIM = "#7E8AB0"     # dim steel-blue labels
RED = "#FF3D6E"         # down / sell → hot pink-red
MAGENTA = "#FF2E9A"     # neon magenta
PURPLE = "#A855F7"      # electric purple


def inject_css() -> None:
    """Cyberpunk neon styling shared by every page."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;800&family=Share+Tech+Mono&family=Inter:wght@400;500;600&display=swap');
        html, body, [class*="css"] {{ font-family:'Inter',sans-serif; font-size:14px; color:{TAN}; }}
        .stApp {{
            background:
              radial-gradient(900px 500px at 12% -10%, rgba(34,227,255,0.10), transparent 60%),
              radial-gradient(900px 500px at 100% 0%, rgba(255,46,154,0.10), transparent 55%),
              {CANVAS};
        }}
        .block-container {{ padding-top: 1.2rem; max-width: 1260px; }}

        /* Headers: techy glow */
        h1, h2, h3 {{ font-family:'Orbitron',sans-serif !important; color:{TAN} !important;
            letter-spacing:1px; text-transform:uppercase; }}
        h2, h3 {{ font-size:1.0rem !important; margin:1.1rem 0 .4rem !important;
            padding-left:.6rem; border-left:3px solid {GOLD};
            text-shadow:0 0 12px rgba(34,227,255,0.35); }}

        /* Hero / page banner */
        .cp-bar {{ position:relative; background:linear-gradient(135deg, rgba(34,227,255,0.07), rgba(255,46,154,0.07));
            border:1px solid {BORDER}; border-radius:12px; padding:1.1rem 1.3rem; margin-bottom:1rem;
            box-shadow:0 0 0 1px rgba(34,227,255,0.08), 0 0 28px rgba(34,227,255,0.08); overflow:hidden; }}
        .cp-bar::before {{ content:""; position:absolute; left:0; top:0; height:100%; width:3px;
            background:linear-gradient(180deg,{GOLD},{MAGENTA}); box-shadow:0 0 16px {GOLD}; }}
        .cp-bar .title {{ font-family:'Orbitron',sans-serif; font-weight:800; font-size:1.5rem;
            letter-spacing:1.5px; text-transform:uppercase; color:{TAN};
            text-shadow:0 0 18px rgba(34,227,255,0.45); }}
        .cp-bar .title .accent {{ color:{GOLD}; }}
        .cp-bar .sub {{ color:{TAN_DIM}; font-size:.84rem; margin-top:.3rem; }}

        /* Stat tiles (neon quote cells) */
        .tos-tiles {{ display:flex; flex-wrap:wrap; gap:10px; margin:.3rem 0 .7rem; }}
        .tos-tile {{ flex:1 1 150px; background:{PANEL}; border:1px solid {BORDER};
            border-radius:9px; padding:.65rem .8rem; box-shadow:inset 0 0 20px rgba(34,227,255,0.04); }}
        .tos-tile .lbl {{ color:{TAN_DIM}; font-size:.64rem; text-transform:uppercase;
            letter-spacing:1px; font-family:'Share Tech Mono',monospace; }}
        .tos-tile .val {{ font-family:'Share Tech Mono',monospace; font-weight:700;
            font-size:1.5rem; margin-top:.15rem; text-shadow:0 0 14px currentColor; }}

        /* Dashboard cards (bordered containers) */
        [data-testid="stVerticalBlockBorderWrapper"] {{ background:{PANEL};
            border:1px solid {BORDER} !important; border-radius:14px;
            box-shadow:0 0 0 1px rgba(255,46,154,0.05), 0 8px 28px rgba(0,0,0,0.45); }}

        [data-testid="stMetric"] {{ background:{PANEL}; border:1px solid {BORDER};
            border-radius:9px; padding:.6rem .8rem; }}
        [data-testid="stMetricLabel"] p {{ color:{TAN_DIM} !important; font-size:.64rem !important;
            text-transform:uppercase; letter-spacing:1px; }}
        [data-testid="stMetricValue"] {{ color:{GOLD} !important; font-family:'Share Tech Mono',monospace !important;
            font-weight:700 !important; text-shadow:0 0 14px rgba(34,227,255,0.5); }}

        /* Buttons: neon gradient + glow */
        .stButton > button, .stFormSubmitButton > button {{
            background:linear-gradient(135deg,{GOLD},{MAGENTA}); color:#05070d; font-weight:700;
            border:none; border-radius:8px; font-family:'Orbitron',sans-serif; text-transform:uppercase;
            letter-spacing:.6px; padding:.5rem 1rem; box-shadow:0 0 18px rgba(34,227,255,0.35); }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{
            color:#05070d; filter:brightness(1.12); box-shadow:0 0 26px rgba(255,46,154,0.5); }}

        /* Sidebar */
        [data-testid="stSidebar"] {{ background:linear-gradient(180deg,#0C0D1A,{PANEL});
            border-right:1px solid {BORDER}; }}
        [data-testid="stSidebarNav"] a span {{ color:{TAN} !important; font-family:'Share Tech Mono',monospace; }}
        .cp-brand {{ display:flex; align-items:center; gap:.6rem; padding:.3rem .2rem .9rem;
            border-bottom:1px solid {BORDER}; margin-bottom:.8rem; }}
        .cp-brand .badge {{ width:34px; height:34px; border-radius:8px;
            background:linear-gradient(135deg,{GOLD},{MAGENTA}); display:flex; align-items:center;
            justify-content:center; font-family:'Orbitron',sans-serif; font-weight:800; color:#05070d;
            box-shadow:0 0 16px rgba(34,227,255,0.5); }}
        .cp-brand .name {{ font-family:'Orbitron',sans-serif; font-weight:700; font-size:.82rem;
            letter-spacing:1px; color:{TAN}; }}
        .cp-brand .tag {{ color:{TAN_DIM}; font-size:.6rem; letter-spacing:2px; text-transform:uppercase; }}

        input, textarea, [data-baseweb="select"] > div {{ border-radius:7px !important;
            font-family:'Share Tech Mono',monospace !important; }}
        [data-testid="stTable"] table {{ border:1px solid {BORDER}; font-family:'Share Tech Mono',monospace;
            font-size:.82rem; }}
        [data-testid="stTable"] th {{ background:{CANVAS}; color:{GOLD} !important;
            text-transform:uppercase; letter-spacing:1px; }}
        [data-testid="stTable"] tr:nth-child(even) td {{ background:rgba(34,227,255,0.03); }}
        a {{ color:{GOLD_SOFT}; }}
        .stAlert {{ border-radius:9px; border:1px solid {BORDER}; }}
        .eyebrow {{ color:{MAGENTA}; font-family:'Share Tech Mono',monospace; font-size:.66rem;
            letter-spacing:2px; text-transform:uppercase; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    # Neon brand badge in the sidebar (on every page).
    st.sidebar.markdown(
        '<div class="cp-brand"><div class="badge">S</div>'
        '<div><div class="name">STOCK//AI</div>'
        '<div class="tag">neural terminal</div></div></div>',
        unsafe_allow_html=True,
    )


def hero(title_html: str, subtitle: str) -> None:
    """Render the neon hero banner (title may include <span class='accent'>)."""
    st.markdown(
        f'<div class="cp-bar"><div class="title">{title_html}</div>'
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

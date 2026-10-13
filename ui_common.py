"""Shared UI theme, cached data helpers, and chart/metric builders for all pages.

One place for the brand palette and the Streamlit caches so every page looks and
behaves identically. Kept import-light: no trading happens at import time.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
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

        /* Smooth interactions */
        .stButton > button, .stFormSubmitButton > button, .tos-tile, .mkt-card,
        [data-testid="stVerticalBlockBorderWrapper"] {{ transition: transform .14s ease, box-shadow .2s ease, border-color .2s ease; }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{ transform: translateY(-1px); }}
        .tos-tile:hover {{ transform: translateY(-2px); border-color:{GOLD}; }}
        [data-testid="stVerticalBlockBorderWrapper"]:hover {{ border-color:{GOLD} !important;
            box-shadow:0 0 0 1px rgba(34,227,255,0.25), 0 10px 34px rgba(0,0,0,0.5); transform: translateY(-2px); }}

        /* Live market grid */
        .mkt-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr));
            gap:12px; margin:.2rem 0 1rem; }}
        .mkt-card {{ background:linear-gradient(160deg, rgba(34,227,255,0.05), rgba(255,46,154,0.04)), {PANEL};
            border:1px solid {BORDER}; border-radius:12px; padding:.7rem .8rem .5rem; }}
        .mkt-card:hover {{ transform:translateY(-3px); border-color:{GOLD};
            box-shadow:0 0 0 1px rgba(34,227,255,0.25), 0 10px 26px rgba(0,0,0,0.5); }}
        .mkt-top {{ display:flex; justify-content:space-between; align-items:center; }}
        .mkt-tkr {{ font-family:'Orbitron',sans-serif; font-weight:700; font-size:.92rem;
            color:{TAN}; letter-spacing:.5px; }}
        .mkt-chg {{ font-family:'Share Tech Mono',monospace; font-size:.76rem; font-weight:700; }}
        .mkt-price {{ font-family:'Share Tech Mono',monospace; font-size:1.25rem; color:{TAN};
            margin:.15rem 0 .1rem; }}
        .mkt-spark {{ line-height:0; margin-top:.2rem; }}
        .mkt-spark svg {{ width:100%; height:38px; }}
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


# --------------------------------------------------------------------------
# Live market overview (watchlist sparklines) — fills the dashboard with real data
# --------------------------------------------------------------------------

WATCHLIST = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM"]


@st.cache_data(ttl=900, show_spinner=False)
def watchlist_quotes(tickers=tuple(WATCHLIST), period="6mo"):
    """Batch-fetch recent closes and return per-ticker quote dicts.

    Returns [{ticker, last, pct, spark:[floats]}] sorted by % change desc.
    One cached yfinance call for the whole list; empty on failure (UI degrades).
    """
    try:
        data = yf.download(list(tickers), period=period, auto_adjust=True,
                           progress=False, group_by="ticker")
    except Exception:  # noqa: BLE001
        return []

    quotes = []
    for t in tickers:
        try:
            close = data[t]["Close"].dropna() if (t in data) else pd.Series(dtype=float)
            if close.empty:
                continue
            spark = close.tail(60).tolist()
            last = float(close.iloc[-1])
            prev = float(close.iloc[-2]) if len(close) > 1 else last
            pct = (last / prev - 1) * 100 if prev else 0.0
            quotes.append({"ticker": t, "last": last, "pct": pct, "spark": spark})
        except Exception:  # noqa: BLE001
            continue
    quotes.sort(key=lambda q: q["pct"], reverse=True)
    return quotes


def _sparkline_svg(values, color, w=150, h=38):
    """Return a compact neon sparkline SVG (area + glowing line) for `values`."""
    if not values or len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1.0
    n = len(values)
    pts = [(i / (n - 1) * w, h - 3 - (v - lo) / rng * (h - 6)) for i, v in enumerate(values)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"0,{h} " + line + f" {w},{h}"
    uid = f"g{abs(hash(tuple(values))) % 100000}"
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<defs><linearGradient id="{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.35"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
        f'<polygon points="{area}" fill="url(#{uid})"/>'
        f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.8" '
        f'stroke-linejoin="round" stroke-linecap="round" '
        f'style="filter:drop-shadow(0 0 4px {color})"/></svg>'
    )


def market_cards(quotes):
    """Render a responsive grid of neon watchlist cards with sparklines."""
    if not quotes:
        st.info("Market data unavailable right now — try again shortly.")
        return
    cells = []
    for q in quotes:
        up = q["pct"] >= 0
        color = GREEN if up else RED
        arrow = "▲" if up else "▼"
        cells.append(
            f'<div class="mkt-card">'
            f'<div class="mkt-top"><span class="mkt-tkr">{q["ticker"]}</span>'
            f'<span class="mkt-chg" style="color:{color}">{arrow} {abs(q["pct"]):.2f}%</span></div>'
            f'<div class="mkt-price">${q["last"]:,.2f}</div>'
            f'<div class="mkt-spark">{_sparkline_svg(q["spark"], color)}</div>'
            f'</div>'
        )
    st.markdown(f'<div class="mkt-grid">{"".join(cells)}</div>', unsafe_allow_html=True)


def eyebrow(text):
    """Small magenta uppercase section label."""
    st.markdown(f'<span class="eyebrow">{text}</span>', unsafe_allow_html=True)


def candle_chart(df, positions=None):
    """Candlestick chart (neon up/down) with optional buy/sell markers on Close."""
    tail = df.tail(260)  # keep it readable/fast
    fig = go.Figure(go.Candlestick(
        x=tail.index, open=tail["Open"], high=tail["High"], low=tail["Low"], close=tail["Close"],
        increasing=dict(line=dict(color=GREEN), fillcolor=GREEN),
        decreasing=dict(line=dict(color=RED), fillcolor=RED), name="OHLC"))
    if positions is not None:
        p = positions.reindex(tail.index).fillna(0)
        changes = p.diff().fillna(p)
        buys, sells = tail.index[changes == 1], tail.index[changes == -1]
        fig.add_trace(go.Scatter(x=buys, y=tail.loc[buys, "Low"] * 0.985, mode="markers",
            name="Buy", marker=dict(symbol="triangle-up", size=11, color=GOLD,
            line=dict(width=1, color=TAN))))
        fig.add_trace(go.Scatter(x=sells, y=tail.loc[sells, "High"] * 1.015, mode="markers",
            name="Sell", marker=dict(symbol="triangle-down", size=11, color=MAGENTA,
            line=dict(width=1, color=TAN))))
    fig.update_layout(xaxis_rangeslider_visible=False)
    _style_fig(fig, "Price ($)")
    return fig

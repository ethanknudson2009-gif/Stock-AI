"""Shared data helpers (cached) and theme-aware chart builders for all pages.

Kept import-light: no trading happens at import time. All styling/colors come
from ui/theme.py.
"""

from datetime import datetime

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
from ui import theme

load_dotenv()
SETTINGS = load_settings()


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


def get_broker():
    """Return (broker, label): the real Alpaca paper broker, or a demo FakeBroker."""
    try:
        from stock_ai.execution.paper import AlpacaPaperBroker

        return AlpacaPaperBroker(), "Alpaca paper account"
    except Exception:  # noqa: BLE001
        return FakeBroker(), "FakeBroker (no Alpaca keys — demo only, empty positions)"


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


@st.cache_data(ttl=900, show_spinner=False)
def watchlist_as_of(tickers=tuple(WATCHLIST)) -> str:
    """Timestamp of the cached watchlist pull (cached alongside it, same TTL)."""
    return datetime.now().strftime("%H:%M")


# ---------------------------------------------------------------- charts ----

def price_chart(test_df, positions):
    """Close-price line with buy / sell markers."""
    c = theme.colors()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=test_df.index, y=test_df["Close"], mode="lines",
                             name="Close", line=dict(color=c["accent"], width=1.8)))
    changes = positions.diff().fillna(positions)
    buys, sells = test_df.index[changes == 1], test_df.index[changes == -1]
    fig.add_trace(go.Scatter(x=buys, y=test_df.loc[buys, "Close"], mode="markers", name="Buy",
                             marker=dict(symbol="triangle-up", size=9, color=c["up"])))
    fig.add_trace(go.Scatter(x=sells, y=test_df.loc[sells, "Close"], mode="markers", name="Sell",
                             marker=dict(symbol="triangle-down", size=9, color=c["down"])))
    return theme.style_fig(fig, "Price ($)")


def equity_chart(cumulative):
    """Equity curve (growth of $1) with a soft accent fill."""
    c = theme.colors()
    fig = go.Figure(go.Scatter(x=cumulative.index, y=cumulative, mode="lines", name="Strategy",
                               line=dict(color=c["accent"], width=1.8),
                               fill="tozeroy", fillcolor=c["accent-soft"]))
    fig.update_yaxes(rangemode="normal")
    return theme.style_fig(fig, "Growth of $1")


def candle_chart(df, positions=None):
    """Candlestick (up/down colors) with optional buy/sell markers."""
    c = theme.colors()
    tail = df.tail(260)
    fig = go.Figure(go.Candlestick(
        x=tail.index, open=tail["Open"], high=tail["High"], low=tail["Low"], close=tail["Close"],
        increasing=dict(line=dict(color=c["up"], width=1), fillcolor=c["up"]),
        decreasing=dict(line=dict(color=c["down"], width=1), fillcolor=c["down"]), name="Price"))
    if positions is not None:
        p = positions.reindex(tail.index).fillna(0)
        changes = p.diff().fillna(p)
        buys, sells = tail.index[changes == 1], tail.index[changes == -1]
        fig.add_trace(go.Scatter(x=buys, y=tail.loc[buys, "Low"] * 0.985, mode="markers", name="Buy",
                                 marker=dict(symbol="triangle-up", size=9, color=c["accent"])))
        fig.add_trace(go.Scatter(x=sells, y=tail.loc[sells, "High"] * 1.015, mode="markers", name="Sell",
                                 marker=dict(symbol="triangle-down", size=9, color=c["text-muted"])))
    fig.update_layout(xaxis_rangeslider_visible=False)
    return theme.style_fig(fig, "Price ($)")

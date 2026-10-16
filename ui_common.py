"""Shared data helpers (cached) and theme-aware chart builders for all pages.

Kept import-light: no trading happens at import time. All styling/colors come
from ui/theme.py.
"""

import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from dotenv import load_dotenv
from plotly.subplots import make_subplots

from stock_ai.backtest.engine import run_backtest
from stock_ai.config import TICKER_SUGGESTIONS, load_settings
from stock_ai.data.loader import fetch_price_history
from stock_ai.execution import FakeBroker
from stock_ai.features.indicators import add_features
from stock_ai.models.classifier import build_labels, latest_signal, train_model, walk_forward_predict
from stock_ai.models.evaluation import block_bootstrap_sharpe, classification_stats, edge_check
from stock_ai.strategy.baselines import buy_hold_positions, sma_crossover_positions
from stock_ai.models.rf_backend import RandomForestBackend
from ui import theme

load_dotenv()
SETTINGS = load_settings()

ET = ZoneInfo("America/New_York")
MAX_START = date(2010, 1, 1)
WARMUP_DAYS = 420          # extra history fetched so 200-day features exist from `start`
MARKET_TTL = 300           # market data cache: 5 minutes
MODEL_TTL = 3600           # trained walk-forward results: 1 hour
COST_GRID_BPS = (0, 5, 10, 25)
RANGES = {"1Y": 365, "3Y": 3 * 365, "5Y": 5 * 365, "Max": None}
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


# ------------------------------------------------------------- time helpers --

def now_et() -> datetime:
    return datetime.now(ET)


def latest_trading_day(now: datetime | None = None) -> date:
    """Most recent weekday whose session has opened (US/Eastern). Holidays aren't
    modeled; on a holiday the data simply ends at the previous session."""
    n = now or now_et()
    d = n.date()
    if n.weekday() >= 5 or n.time() < time(9, 30):
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def range_start(label: str, end: date) -> date:
    days = RANGES.get(label)
    return MAX_START if days is None else end - timedelta(days=days)


def fmt_stamp(dt: datetime) -> str:
    """'10:24 AM EDT'."""
    return dt.strftime("%-I:%M %p %Z")


def valid_ticker(t: str) -> bool:
    return bool(_TICKER_RE.match(t or ""))


def parse_tickers(raw: str) -> list[str]:
    seen, out = set(), []
    for t in raw.replace("\n", ",").replace(" ", ",").split(","):
        t = t.strip().upper()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


# ------------------------------------------------------------- data helpers --

@st.cache_data(ttl=MARKET_TTL, show_spinner=False)
def _download(ticker: str, start: date, end: date) -> pd.DataFrame:
    # yfinance's `end` is exclusive, so ask for the day after to include `end`.
    return fetch_price_history(ticker, start.isoformat(), (end + timedelta(days=1)).isoformat())


@st.cache_data(ttl=MARKET_TTL, show_spinner=False)
def market_close(start: date, end: date) -> pd.Series | None:
    """SPY closes for the market-regime feature (None if unavailable)."""
    try:
        return _download("SPY", start, end)["Close"]
    except Exception:  # noqa: BLE001
        return None


@st.cache_data(ttl=MARKET_TTL, show_spinner=False)
def load_prices(ticker: str, start: date, end: date) -> pd.DataFrame:
    """Featured daily history from `start` to `end` (warm-up fetched, then trimmed)."""
    warm = start - timedelta(days=WARMUP_DAYS)
    feats = add_features(_download(ticker, warm, end), market_close=market_close(warm, end))
    feats = feats.loc[feats.index >= pd.Timestamp(start)]
    if len(feats) < 120:
        raise ValueError(f"Not enough history for {ticker} in this range — try a longer range.")
    return feats


@st.cache_data(ttl=MODEL_TTL, show_spinner=False)
def walk_forward(ticker: str, start: date, end: date) -> dict:
    """Cached walk-forward run: OOS P(up), realized labels, accuracy."""
    df = load_prices(ticker, start, end)
    proba, acc = walk_forward_predict(df)
    labels = build_labels(df)["label"].reindex(proba.index)
    return {"proba": proba, "accuracy": acc, "labels": labels}


def analyze(ticker: str, start: date, end: date, threshold: float, cost_bps: float,
            view_from: date | None = None) -> dict:
    """Everything a results page needs for one ticker (heavy parts come from caches).

    The edge check judges the model's whole out-of-sample record; `view_from` only crops
    the window the return/Sharpe numbers are computed over.
    """
    df = load_prices(ticker, start, end)
    wf = walk_forward(ticker, start, end)
    proba_all, labels_all = wf["proba"], wf["labels"]
    edge = edge_check(proba_all, labels_all)
    first_oos = proba_all.index[0].date()
    proba = proba_all if view_from is None else proba_all[proba_all.index >= pd.Timestamp(view_from)]
    if len(proba) < 60:
        raise ValueError("That 'Results from' date leaves too little data — pick an earlier date.")
    wf_df = df.loc[proba.index]
    pos = (proba > threshold).astype(int)
    sma_pos = sma_crossover_positions(df).reindex(wf_df.index).fillna(0).astype(int)
    runs = {"Model (walk-forward)": (pos, run_backtest(wf_df, pos, cost_bps=cost_bps)),
            "Buy & hold": (buy_hold_positions(wf_df), run_backtest(wf_df, buy_hold_positions(wf_df), cost_bps=cost_bps)),
            "SMA 50/200 crossover": (sma_pos, run_backtest(wf_df, sma_pos, cost_bps=cost_bps))}
    for name, (_p, r) in runs.items():
        r["sharpe_ci"] = block_bootstrap_sharpe(r["cumulative_returns"].pct_change().fillna(r["cumulative_returns"].iloc[0] - 1))
    sens = {bps: run_backtest(wf_df, pos, cost_bps=bps) for bps in COST_GRID_BPS}
    p_today, d_today = today_signal(ticker, start, end)
    return {"df": df, "wf_df": wf_df, "proba": proba, "pos": pos, "runs": runs, "sens": sens, "edge": edge,
            "cls": classification_stats(proba, labels_all, threshold), "first_oos": first_oos,
            "p_today": p_today, "d_today": d_today, "hist_up": edge["base_rate"],
            "bh_zero_cost": run_backtest(wf_df, buy_hold_positions(wf_df), cost_bps=0)}


@st.cache_data(ttl=MODEL_TTL, show_spinner=False)
def today_signal(ticker: str, start: date, end: date) -> tuple[float, pd.Timestamp]:
    return latest_signal(load_prices(ticker, start, end))


@st.cache_resource(show_spinner=False)
def in_sample(ticker: str, start: date, end: date):
    """(backend, train_df) from a single split — used only for the in-sample contrast."""
    model, _acc, train_df, _test = train_model(load_prices(ticker, start, end))
    return RandomForestBackend.from_fitted(model), train_df


@st.cache_data(ttl=MARKET_TTL, show_spinner=False)
def watchlist_quotes(tickers: tuple[str, ...], period: str = "6mo"):
    """(quotes, fetched_at). quotes = [{ticker, last, pct, spark}], sorted by % change."""
    fetched_at = now_et()
    try:
        data = yf.download(list(tickers), period=period, auto_adjust=True,
                           progress=False, group_by="ticker")
    except Exception:  # noqa: BLE001
        return [], fetched_at
    quotes = []
    for t in tickers:
        try:
            close = data[t]["Close"].dropna()
            if len(close) < 2:
                continue
            last, prev = float(close.iloc[-1]), float(close.iloc[-2])
            quotes.append({"ticker": t, "last": last, "pct": (last / prev - 1) * 100,
                           "spark": close.tail(60).tolist(), "date": close.index[-1]})
        except Exception:  # noqa: BLE001
            continue
    quotes.sort(key=lambda q: q["pct"], reverse=True)
    return quotes, fetched_at


@st.cache_data(ttl=MARKET_TTL, show_spinner=False)
def latest_prices(tickers: tuple[str, ...]) -> dict[str, float]:
    """Latest close per ticker (for order-size estimates)."""
    if not tickers:
        return {}
    data = yf.download(list(tickers), period="7d", auto_adjust=True, progress=False, group_by="ticker")
    out = {}
    for t in tickers:
        try:
            out[t] = float(data[t]["Close"].dropna().iloc[-1])
        except Exception:  # noqa: BLE001
            continue
    return out


def get_broker():
    """Return (broker, label): the real Alpaca paper broker, or a demo FakeBroker."""
    try:
        from stock_ai.execution.paper import AlpacaPaperBroker

        return AlpacaPaperBroker(), "Alpaca paper account"
    except Exception:  # noqa: BLE001
        return FakeBroker(), "FakeBroker (no Alpaca keys — demo only, empty positions)"


# ------------------------------------------------------------------ charts --

def price_chart(df, positions, proba=None, show_signals=True):
    """Price over the OOS window: candlesticks for short windows, a line for long
    ones (candles become unreadable past ~300 sessions). Small markers + tooltips."""
    c = theme.colors()
    fig = go.Figure()
    if len(df) <= 300:
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Price",
            increasing=dict(line=dict(color=c["up"], width=1), fillcolor=c["up"]),
            decreasing=dict(line=dict(color=c["down"], width=1), fillcolor=c["down"])))
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines", name="Close",
                                 line=dict(color=c["text-muted"], width=1.3),
                                 hovertemplate="%{x|%b %d, %Y}<br>$%{y:,.2f}<extra></extra>"))
    if show_signals:
        changes = positions.diff().fillna(positions)
        p = proba.reindex(df.index) if proba is not None else pd.Series(float("nan"), index=df.index)
        for kind, val, sym, color in (("Buy", 1, "triangle-up", c["accent"]), ("Sell", -1, "triangle-down", c["text-faint"])):
            idx = df.index[changes == val]
            fig.add_trace(go.Scatter(
                x=idx, y=df.loc[idx, "Close"], mode="markers", name=kind, customdata=p.loc[idx],
                marker=dict(symbol=sym, size=7, color=color, line=dict(width=0)),
                hovertemplate=f"<b>{kind}</b> · %{{x|%b %d, %Y}}<br>$%{{y:,.2f}}<br>P(up) %{{customdata:.0%}}<extra></extra>"))
    fig.update_layout(xaxis_rangeslider_visible=False)
    return theme.style_fig(fig, height=400)


def equity_chart(curves: dict, drawdown_of: str | None = None):
    """Growth-of-$1 lines (autoscaled, dashed 1.0 baseline) + shaded drawdown panel."""
    c = theme.colors()
    styles = [dict(color=c["accent"], width=2), dict(color=c["text-muted"], width=1.5),
              dict(color=c["text-faint"], width=1.3, dash="dot"), dict(color=c["up"], width=1.3),
              dict(color=c["down"], width=1.3, dash="dash")]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.05)
    for (name, series), style in zip(curves.items(), styles):
        fig.add_trace(go.Scatter(x=series.index, y=series, mode="lines", name=name, line=style,
                                 hovertemplate=f"{name}<br>%{{x|%b %d, %Y}}<br>%{{y:.2f}}×<extra></extra>"), row=1, col=1)
    fig.add_hline(y=1.0, line=dict(color=c["text-faint"], width=1, dash="dash"), row=1, col=1)
    dd_name = drawdown_of or next(iter(curves))
    eq = curves[dd_name]
    dd = eq / eq.cummax() - 1
    fig.add_trace(go.Scatter(x=dd.index, y=dd, mode="lines", name=f"{dd_name} drawdown", showlegend=False,
                             line=dict(color=c["down"], width=1), fill="tozeroy", fillcolor=c["down-soft"],
                             hovertemplate="Drawdown %{y:.1%}<extra></extra>"), row=2, col=1)
    fig.update_yaxes(tickformat=".0%", row=2, col=1)
    return theme.style_fig(fig, height=440)


def contribution_chart(contrib: pd.Series):
    """Horizontal bars: each ticker's summed daily contribution to portfolio return."""
    c = theme.colors()
    s = contrib[contrib != 0].sort_values()
    fig = go.Figure(go.Bar(x=s.values, y=s.index, orientation="h",
                           marker_color=[c["up"] if v >= 0 else c["down"] for v in s.values],
                           hovertemplate="%{y}: %{x:+.1%}<extra></extra>"))
    fig.update_xaxes(tickformat=".0%")
    return theme.style_fig(fig, height=max(240, 22 * len(s) + 60))


def cost_sensitivity_chart(sens: dict, bh_return: float):
    """Strategy total return at several trading-cost levels vs. buy & hold: how fragile is the edge?"""
    c = theme.colors()
    xs = [f"{b} bps" for b in sens]
    ys = [r["total_return"] for r in sens.values()]
    sharpes = [r["sharpe_ratio"] for r in sens.values()]
    fig = go.Figure(go.Bar(
        x=xs, y=ys, marker_color=[c["up"] if y >= bh_return else c["accent"] for y in ys], customdata=sharpes,
        text=[f"{y:+.0%}" for y in ys], textposition="outside", name="Strategy",
        hovertemplate="%{x}<br>return %{y:+.1%}<br>Sharpe %{customdata:.2f}<extra></extra>"))
    fig.add_hline(y=bh_return, line=dict(color=c["text-muted"], width=1.5, dash="dash"),
                  annotation_text=f"Buy & hold {bh_return:+.0%}", annotation_position="top left",
                  annotation_font_color=c["text-muted"])
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(showlegend=False)
    return theme.style_fig(fig, height=300)


@st.cache_data(ttl=MARKET_TTL, show_spinner=False)
def recent_closes(tickers: tuple[str, ...], start: str) -> dict[str, pd.Series]:
    """Daily closes since `start` per ticker (to resolve logged signals against what happened)."""
    out = {}
    for t in tickers:
        try:
            out[t] = _download(t, date.fromisoformat(start), latest_trading_day())["Close"]
        except Exception:  # noqa: BLE001
            continue
    return out


def has_edge(ticker: str) -> bool | None:
    """Does the model beat the base rate on `ticker` over the full history? None if it can't be judged."""
    try:
        wf = walk_forward(ticker, MAX_START, latest_trading_day())
        return edge_check(wf["proba"], wf["labels"])["has_edge"]
    except Exception:  # noqa: BLE001
        return None


@st.cache_data(ttl=MARKET_TTL, show_spinner=False)
def news_for(symbols: tuple[str, ...], days: int, use_llm: bool = False) -> pd.DataFrame:
    """Cached Alpaca news for a universe (refreshes every 5 minutes); Claude scores are cached on disk too."""
    from stock_ai.data.news import fetch_news  # noqa: PLC0415

    return fetch_news(list(symbols), days=days, use_llm=use_llm)


@st.cache_data(ttl=60, show_spinner=False)
def account_snapshot() -> dict | None:
    """Everything the My Trades page shows, straight from the Alpaca paper account (None without keys).

    Cached for a minute so reruns are instant; the page's Refresh button clears it.
    """
    try:
        from stock_ai.execution.paper import AlpacaPaperBroker  # noqa: PLC0415

        b = AlpacaPaperBroker()
        return {"account": b.get_account_summary(), "positions": b.get_position_details(),
                "orders": b.get_order_history(100), "equity": b.get_equity_history("3M"), "fetched": now_et()}
    except ValueError:
        return None  # no keys


def equity_history_chart(points: list[tuple]):
    """Account equity over time (Alpaca portfolio history)."""
    c = theme.colors()
    xs = [datetime.fromtimestamp(t, ET) for t, _ in points]
    ys = [e for _, e in points]
    fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines+markers", line=dict(color=c["accent"], width=2),
                               marker=dict(size=5), hovertemplate="%{x|%b %d}<br>$%{y:,.2f}<extra></extra>"))
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    return theme.style_fig(fig, height=300)

"""Streamlit backtest explorer — reproduce the single-ticker CLI backtest in a browser.

Run:  streamlit run app.py   (opens http://localhost:8501)

Secrets rule: load_dotenv() is called here (one of the three allowed entry
points) and keys are only ever read through stock_ai.config.load_settings().
Streamlit's showErrorDetails is off (.streamlit/config.toml) and every
backtest is wrapped so a thrown error is scrubbed before it reaches the page.
"""

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from stock_ai.backtest.engine import run_backtest
from stock_ai.config import load_settings
from stock_ai.data.loader import fetch_price_history
from stock_ai.features.indicators import add_features
from stock_ai.models.classifier import train_model
from stock_ai.models.rf_backend import RandomForestBackend
from stock_ai.strategy.signal import generate_signals

load_dotenv()
SETTINGS = load_settings()

st.set_page_config(page_title="Stock-AI Backtest Explorer", layout="wide")
st.title("📈 Stock-AI — Backtest Explorer")
st.caption(
    "Honest out-of-sample backtest of the RandomForest signal. "
    "In-sample numbers are shown too, so the overfitting gap is visible."
)


@st.cache_data(ttl=3600, show_spinner=False)
def _load_prices(ticker: str, start: str, end: str):
    """Cached yfinance fetch + feature engineering. Keyed by (ticker, start, end)."""
    df = fetch_price_history(ticker, start, end)
    return add_features(df)


@st.cache_resource(show_spinner=False)
def _train(ticker: str, start: str, end: str):
    """Cached training. Returns (backend, accuracy, train_df, test_df). One model per key."""
    df = _load_prices(ticker, start, end)
    model, accuracy, train_df, test_df = train_model(df)
    return RandomForestBackend.from_fitted(model), accuracy, train_df, test_df


def _price_chart(test_df, positions):
    """Plotly close-price line with buy (entry) / sell (exit) markers on the test slice."""
    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=test_df.index, y=test_df["Close"], mode="lines",
            name="Close", line=dict(color="#4c78a8"),
        )
    )
    changes = positions.diff().fillna(positions)
    buys = test_df.index[changes == 1]
    sells = test_df.index[changes == -1]
    fig.add_trace(
        go.Scattergl(
            x=buys, y=test_df.loc[buys, "Close"], mode="markers", name="Buy",
            marker=dict(symbol="triangle-up", size=11, color="#2ca02c"),
        )
    )
    fig.add_trace(
        go.Scattergl(
            x=sells, y=test_df.loc[sells, "Close"], mode="markers", name="Sell",
            marker=dict(symbol="triangle-down", size=11, color="#d62728"),
        )
    )
    fig.update_layout(
        height=430, margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1.02, yanchor="bottom"),
        xaxis_title=None, yaxis_title="Price ($)",
    )
    return fig


with st.sidebar:
    st.header("Backtest settings")
    with st.form("backtest_form"):
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        start = st.text_input("Start date (YYYY-MM-DD)", value="2015-01-01")
        end = st.text_input("End date (YYYY-MM-DD)", value="2026-10-12")
        cost_bps = st.slider("Cost per trade (bps)", 0.0, 50.0, 10.0, 1.0)
        threshold = st.slider("Confidence threshold", 0.50, 0.70, 0.50, 0.01)
        backend_choice = st.selectbox("Model backend", ["RandomForest", "Jev (coming in Phase H)"])
        submitted = st.form_submit_button("Run Backtest", width='stretch')

if not submitted:
    st.info("Set your options in the sidebar and click **Run Backtest**.")
    st.stop()

if backend_choice.startswith("Jev"):
    st.warning("The Jev backend isn't built yet (Phase H). Running RandomForest instead.")

try:
    with st.spinner(f"Fetching {ticker} and training…"):
        backend, accuracy, train_df, test_df = _train(ticker, start, end)

        oos_positions = generate_signals(backend, test_df, threshold=threshold)
        oos = run_backtest(test_df, oos_positions, cost_bps=cost_bps)
        is_positions = generate_signals(backend, train_df, threshold=threshold)
        is_results = run_backtest(train_df, is_positions, cost_bps=cost_bps)
except Exception as exc:  # noqa: BLE001 — surface a redacted message, never a raw traceback
    st.error(SETTINGS.scrub(f"Backtest failed: {type(exc).__name__}: {exc}"))
    st.stop()


def _metrics_row(res, accuracy=None):
    cols = st.columns(5)
    if accuracy is not None:
        cols[0].metric("Test accuracy", f"{accuracy:.1%}")
    else:
        cols[0].metric("Test accuracy", "—")
    cols[1].metric("Strategy return", f"{res['total_return']:.1%}")
    cols[2].metric("Buy & hold", f"{res['buy_hold_return']:.1%}")
    cols[3].metric("Sharpe", f"{res['sharpe_ratio']:.2f}")
    cols[4].metric("Max drawdown", f"{res['max_drawdown']:.1%}")
    st.caption(f"{res['n_trades']} trades @ {res['cost_bps']:.0f} bps")


st.subheader("✅ Out-of-sample (honest)")
st.caption(f"{test_df.index[0].date()} → {test_df.index[-1].date()} — signals on held-out data the model never trained on.")
_metrics_row(oos, accuracy)

delta = oos["total_return"] - oos["buy_hold_return"]
(st.success if delta >= 0 else st.warning)(
    f"Strategy {'beat' if delta >= 0 else 'trailed'} buy & hold by {abs(delta):.1%} out-of-sample."
)

st.plotly_chart(_price_chart(test_df, oos_positions), width='stretch')

with st.expander("⚠️ In-sample (training data — overfitting-prone, not a real result)"):
    st.caption(f"{train_df.index[0].date()} → {train_df.index[-1].date()} — the model saw this data while training, so these numbers flatter it.")
    _metrics_row(is_results)

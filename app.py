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

import bot
from stock_ai.backtest.engine import run_backtest
from stock_ai.backtest.multi_engine import backtest_universe
from stock_ai.config import DEFAULT_UNIVERSE, load_settings
from stock_ai.data.loader import fetch_price_history
from stock_ai.execution import FakeBroker
from stock_ai.features.indicators import add_features
from stock_ai.models.classifier import train_model
from stock_ai.models.rf_backend import RandomForestBackend
from stock_ai.strategy.signal import generate_signals


def _get_broker():
    """Return (broker, label). Prefer the real Alpaca paper broker; fall back to a
    demo FakeBroker when keys are missing so the preview flow still works offline."""
    try:
        from stock_ai.execution.paper import AlpacaPaperBroker

        return AlpacaPaperBroker(), "Alpaca paper account"
    except Exception:  # noqa: BLE001 — no/invalid keys → safe demo broker
        return FakeBroker(), "FakeBroker (no Alpaca keys — demo only, empty positions)"

load_dotenv()
SETTINGS = load_settings()

st.set_page_config(page_title="Stock-AI Analyzer", page_icon="📈", layout="wide")

# --- Brand palette: gold / green / tan ---
GOLD = "#CBA135"
GOLD_SOFT = "#E3C56B"
GREEN = "#2E7D4F"
GREEN_DEEP = "#15271B"
TAN = "#EADFC6"
TAN_DIM = "#B9AC8C"
RED = "#C0564B"


def _inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap');

        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
        .block-container {{ padding-top: 2.2rem; max-width: 1150px; }}

        /* Hero banner */
        .hero {{
            background: linear-gradient(135deg, {GREEN_DEEP} 0%, #1c3326 55%, #24422f 100%);
            border: 1px solid rgba(203,161,53,0.35);
            border-radius: 18px;
            padding: 1.6rem 1.9rem;
            margin-bottom: 1.4rem;
            box-shadow: 0 8px 28px rgba(0,0,0,0.35);
        }}
        .hero h1 {{
            font-family: 'Fraunces', serif;
            font-weight: 700; font-size: 2.35rem; line-height: 1.05;
            margin: 0; color: {TAN};
            letter-spacing: -0.5px;
        }}
        .hero h1 .accent {{ color: {GOLD}; }}
        .hero p {{ color: {TAN_DIM}; margin: 0.5rem 0 0; font-size: 0.98rem; }}
        .hero .pill {{
            display:inline-block; margin-top:0.9rem; padding:0.28rem 0.8rem;
            background: rgba(203,161,53,0.14); border:1px solid rgba(203,161,53,0.4);
            color:{GOLD_SOFT}; border-radius:999px; font-size:0.78rem; font-weight:600;
            letter-spacing:0.3px;
        }}

        /* Section headers */
        h2, h3 {{ font-family: 'Fraunces', serif !important; color: {TAN} !important; }}

        /* Metric cards */
        [data-testid="stMetric"] {{
            background: {GREEN_DEEP};
            border: 1px solid rgba(203,161,53,0.22);
            border-radius: 14px;
            padding: 0.9rem 1rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.25);
        }}
        [data-testid="stMetricLabel"] p {{ color: {TAN_DIM} !important; font-weight:600; font-size:0.78rem; }}
        [data-testid="stMetricValue"] {{ color: {GOLD_SOFT} !important; font-weight:700; }}

        /* Buttons */
        .stButton > button, .stFormSubmitButton > button {{
            background: linear-gradient(135deg, {GOLD} 0%, #b58a28 100%);
            color: #1a1205; font-weight: 700; border: none; border-radius: 10px;
            padding: 0.55rem 1rem; transition: transform .05s ease, filter .15s ease;
        }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{
            filter: brightness(1.08); color:#1a1205; transform: translateY(-1px);
        }}

        /* Sidebar */
        [data-testid="stSidebar"] {{
            background: {GREEN_DEEP};
            border-right: 1px solid rgba(203,161,53,0.18);
        }}
        [data-testid="stSidebar"] h2 {{ color: {GOLD_SOFT} !important; }}

        /* Inputs */
        input, textarea, [data-baseweb="select"] > div {{ border-radius: 9px !important; }}

        /* Tables */
        [data-testid="stTable"] table {{ border-radius: 10px; overflow: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_css()
st.markdown(
    f"""
    <div class="hero">
      <h1>Stock <span class="accent">AI</span> Analyzer</h1>
      <p>Honest, walk-forward backtests of the signal — in-sample numbers shown too, so the overfitting gap stays visible.</p>
      <span class="pill">GOLD · GREEN · TAN</span>
    </div>
    """,
    unsafe_allow_html=True,
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


@st.cache_data(ttl=3600, show_spinner=False)
def _run_universe(tickers: tuple[str, ...], start: str, end: str, top_n: int, cost_bps: float):
    """Cached multi-ticker cross-sectional backtest. Returns (results, equity_curve)."""
    frames = {}
    skipped = []
    for ticker in tickers:
        try:
            frames[ticker] = _load_prices(ticker, start, end)
        except Exception:  # noqa: BLE001 — a bad/empty ticker shouldn't sink the run
            skipped.append(ticker)
    results, _proba, _returns = backtest_universe(
        frames, RandomForestBackend, top_n_count=top_n, cost_bps=cost_bps
    )
    return results, results["cumulative_returns"], skipped


def _equity_chart(cumulative):
    """Plotly equity curve for the portfolio (growth of $1)."""
    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=cumulative.index, y=cumulative, mode="lines",
            name="Portfolio", line=dict(color=GOLD, width=2),
        )
    )
    _style_fig(fig, yaxis_title="Growth of $1")
    return fig


def _style_fig(fig, yaxis_title: str):
    """Apply the brand look (transparent bg, tan fonts, subtle grid) to a figure."""
    fig.update_layout(
        height=430, margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1.02, yanchor="bottom"),
        xaxis_title=None, yaxis_title=yaxis_title,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TAN),
    )
    fig.update_xaxes(gridcolor="rgba(234,223,198,0.08)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(234,223,198,0.08)", zeroline=False)


def _price_chart(test_df, positions):
    """Plotly close-price line with buy (entry) / sell (exit) markers on the test slice."""
    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=test_df.index, y=test_df["Close"], mode="lines",
            name="Close", line=dict(color=GOLD, width=2),
        )
    )
    changes = positions.diff().fillna(positions)
    buys = test_df.index[changes == 1]
    sells = test_df.index[changes == -1]
    fig.add_trace(
        go.Scattergl(
            x=buys, y=test_df.loc[buys, "Close"], mode="markers", name="Buy",
            marker=dict(symbol="triangle-up", size=11, color=GREEN,
                        line=dict(width=1, color=TAN)),
        )
    )
    fig.add_trace(
        go.Scattergl(
            x=sells, y=test_df.loc[sells, "Close"], mode="markers", name="Sell",
            marker=dict(symbol="triangle-down", size=11, color=RED,
                        line=dict(width=1, color=TAN)),
        )
    )
    _style_fig(fig, yaxis_title="Price ($)")
    return fig


with st.sidebar:
    st.header("Backtest settings")
    with st.form("backtest_form"):
        mode = st.radio(
            "Mode",
            ["Single ticker", "Multi-ticker (cross-sectional)", "Paper trade (preview)"],
        )
        ticker = st.text_input("Ticker (single-ticker mode)", value="AAPL").strip().upper()
        tickers_raw = st.text_area(
            "Tickers (multi-ticker mode, comma-separated — blank = Default Universe)",
            value="",
            help=f"Default Universe = {len(DEFAULT_UNIVERSE)} large-cap US stocks.",
        )
        top_n = st.slider("Top-N held (multi-ticker mode)", 1, 15, 5, 1)
        start = st.text_input("Start date (YYYY-MM-DD)", value="2015-01-01")
        end = st.text_input("End date (YYYY-MM-DD)", value="2026-10-12")
        cost_bps = st.slider("Cost per trade (bps)", 0.0, 50.0, 10.0, 1.0)
        threshold = st.slider("Confidence threshold (single-ticker mode)", 0.50, 0.70, 0.50, 0.01)
        backend_choice = st.selectbox("Model backend", ["RandomForest", "Jev (coming in Phase H)"])
        submit_label = "Preview orders" if mode.startswith("Paper") else "Run Backtest"
        submitted = st.form_submit_button(submit_label, width='stretch')

if not submitted:
    st.info("Set your options in the sidebar and click **Run Backtest**.")
    st.stop()

if backend_choice.startswith("Jev"):
    st.warning("The Jev backend isn't built yet (Phase H). Running RandomForest instead.")


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


if mode.startswith("Paper"):
    universe = [
        t.strip().upper() for t in tickers_raw.replace("\n", ",").split(",") if t.strip()
    ] or list(DEFAULT_UNIVERSE)
    broker, broker_label = _get_broker()
    st.subheader("🧾 Paper trade — preview & confirm")
    st.caption(f"Broker: {broker_label}")
    dry = bot.dry_run_enabled()
    (st.info if dry else st.warning)(
        "DRY_RUN is ON — orders will be logged, not sent."
        if dry else
        "DRY_RUN is OFF — confirming will place real paper orders."
    )

    try:
        with st.spinner(f"Computing today's signals for {len(universe)} tickers…"):
            orders = bot.plan_orders(broker, universe=universe, top_n_count=top_n)
            bot.enforce_caps(orders)
    except Exception as exc:  # noqa: BLE001 — redacted, never a raw traceback
        st.error(SETTINGS.scrub(f"Could not build orders: {type(exc).__name__}: {exc}"))
        st.stop()

    st.session_state["pending_orders"] = orders
    if not orders:
        st.success("No changes needed — target holdings already match current positions.")
        st.stop()

    st.write(f"**{len(orders)} intended orders** for {bot.trading_day_today()}:")
    st.table(
        [{"ticker": o.ticker, "side": o.side, "notional": o.notional, "qty": o.qty} for o in orders]
    )

    if st.button("Confirm & submit", type="primary"):
        pending = st.session_state.get("pending_orders") or []
        try:
            result = bot.submit_orders(broker, pending)  # submits EXACTLY what was previewed
        except Exception as exc:  # noqa: BLE001
            st.error(SETTINGS.scrub(f"Submit failed: {type(exc).__name__}: {exc}"))
            st.stop()
        if result["status"] == "dry_run":
            st.success(f"DRY_RUN: logged {result['planned']} orders to logs/orders.csv — none sent.")
        elif result["status"] == "halted":
            st.error(f"Halted: {result['reason']}.")
        else:
            st.success(f"Submitted {result['submitted']} paper orders.")
    st.stop()


if mode.startswith("Multi"):
    tickers = tuple(
        t.strip().upper() for t in tickers_raw.replace("\n", ",").split(",") if t.strip()
    ) or tuple(DEFAULT_UNIVERSE)
    try:
        with st.spinner(f"Fetching & training {len(tickers)} tickers…"):
            res, equity, skipped = _run_universe(tickers, start, end, top_n, cost_bps)
    except Exception as exc:  # noqa: BLE001 — surface a redacted message, never a raw traceback
        st.error(SETTINGS.scrub(f"Backtest failed: {type(exc).__name__}: {exc}"))
        st.stop()

    st.subheader("✅ Portfolio out-of-sample (honest)")
    st.caption(
        f"Equal-weight top-{top_n}, daily rebalance, {res['n_days']} sessions. "
        f"Held ~{res['avg_positions']:.1f} names/day. "
        "Survivorship-biased: the universe is a current snapshot."
    )
    cols = st.columns(4)
    cols[0].metric("Portfolio return", f"{res['total_return']:.1%}")
    cols[1].metric("Equal-weight-all", f"{res['buy_hold_return']:.1%}")
    cols[2].metric("Portfolio Sharpe", f"{res['portfolio_sharpe']:.2f}")
    cols[3].metric("Max drawdown", f"{res['max_drawdown']:.1%}")
    st.caption(
        "Portfolio Sharpe (equal-weight top-N, daily rebalance) — computed on the "
        "combined daily return series, not an average of per-ticker Sharpes."
    )
    if skipped:
        st.warning(f"Skipped (no data): {', '.join(skipped)}")

    delta = res["total_return"] - res["buy_hold_return"]
    (st.success if delta >= 0 else st.warning)(
        f"Top-{top_n} strategy {'beat' if delta >= 0 else 'trailed'} the "
        f"equal-weight-all benchmark by {abs(delta):.1%}."
    )
    st.plotly_chart(_equity_chart(equity), width='stretch')
    st.stop()


# ---- Single-ticker mode ----
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

"""Single-ticker backtest page: walk-forward results, baselines, diagnostics, today's signal."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from stock_ai.backtest.engine import run_backtest
from stock_ai.models.classifier import LABEL_HORIZON
from stock_ai.models.evaluation import classification_stats
from stock_ai.strategy.baselines import buy_hold_positions, sma_crossover_positions
from stock_ai.strategy.signal import generate_signals
from ui.components import (confusion_matrix, data_table, note, page_head, section, signal_card,
                           stat_grid, tone, verdict)
from ui_common import (RANGES, SETTINGS, equity_chart, in_sample, latest_trading_day, load_prices,
                       price_chart, range_start, today_signal, valid_ticker, walk_forward)

COST_HELP = ("What you pay every time you buy or sell, in basis points. 1 bp = 0.01%, so 10 bps "
             "means 0.10% of each trade lost to commissions and slippage.")
THR_HELP = ("How sure the model must be before it buys. 0.50 = buy whenever it thinks 'up' is more "
            "likely than 'down'; 0.60 = only when it's at least 60% sure. Higher = fewer, pickier trades.")

ss = st.session_state
END = latest_trading_day()

# Preload a ticker from Home (search box or a clicked card), once per arrival.
pre = ss.pop("preload_ticker", None) or st.query_params.get("ticker")
if pre and ss.get("_applied_preload") != pre:
    ss["_applied_preload"] = pre
    ss["st_ticker"] = pre.upper()
    ss.setdefault("st_end", END)
    ss.setdefault("st_start", range_start("Max", END))
    ss["st_run"] = (pre.upper(), ss["st_start"], ss["st_end"]) if valid_ticker(pre.upper()) else None
ss.setdefault("st_ticker", "AAPL")
ss.setdefault("st_range", "Max")
ss.setdefault("st_end", END)
ss.setdefault("st_start", range_start("Max", END))


def _apply_range():
    if ss.get("st_range"):
        ss["st_start"] = range_start(ss["st_range"], ss["st_end"])


def _custom_dates():
    ss["st_range"] = None


page_head("Single Ticker", "Walk-forward backtest of one stock against simple baselines, plus today's model call.",
          eyebrow="Backtest")

with st.container(key="controls_single"):
    c = st.columns([1.1, 1.5, 1, 1])
    c[0].text_input("Ticker", key="st_ticker", help="Any US-listed symbol, e.g. AAPL, MSFT, BRK-B.")
    c[1].segmented_control("Range", list(RANGES), key="st_range", on_change=_apply_range)
    c[2].date_input("Start", key="st_start", min_value=date(1990, 1, 1), max_value=END, on_change=_custom_dates)
    c[3].date_input("End", key="st_end", max_value=END, on_change=_custom_dates,
                    help=f"Defaults to the latest trading day ({END:%b %d, %Y}).")
    c2 = st.columns([1, 1, 0.7], vertical_alignment="bottom")
    cost_bps = c2[0].slider("Cost per trade (bps)", 0.0, 50.0, 10.0, 1.0, key="st_cost", help=COST_HELP)
    threshold = c2[1].slider("Confidence threshold", 0.50, 0.70, 0.50, 0.01, key="st_thr", help=THR_HELP)
    run = c2[2].button("Run backtest", icon=":material/play_arrow:", width="stretch")

if run:
    t = ss["st_ticker"].strip().upper()
    if not valid_ticker(t):
        st.error(f"“{ss['st_ticker']}” doesn't look like a ticker. Use letters like AAPL, MSFT or BRK-B.")
    elif ss["st_end"] - ss["st_start"] < timedelta(days=330):
        st.error("Pick a range of at least about a year — the model needs history to learn from.")
    else:
        ss["st_run"] = (t, ss["st_start"], ss["st_end"])

if not ss.get("st_run"):
    st.info("Pick a ticker and range, then click **Run backtest**. Works for any US-listed stock.")
    st.stop()

ticker, start, end = ss["st_run"]
if (ss["st_ticker"].strip().upper(), ss["st_start"], ss["st_end"]) != (ticker, start, end):
    note(f"Showing {ticker} {start:%b %Y}–{end:%b %Y}. Click Run backtest to apply your new ticker or dates.")

try:
    with st.spinner(f"Training walk-forward models for {ticker}… (first run takes a few seconds)"):
        df = load_prices(ticker, start, end)
        wf = walk_forward(ticker, start, end)
        p_today, d_today = today_signal(ticker, start, end)
except ValueError as exc:
    msg = str(exc)
    if "No price data" in msg:
        st.error(f"We couldn't find price data for **{ticker}**. Check the symbol (e.g. BRK-B, not BRK.B).")
    else:
        st.error(SETTINGS.scrub(msg))
    st.stop()
except Exception as exc:  # noqa: BLE001
    st.error(SETTINGS.scrub(f"Backtest failed: {type(exc).__name__}: {exc}"))
    st.stop()

proba = wf["proba"]
wf_df = df.loc[proba.index]
pos = (proba > threshold).astype(int)
model = run_backtest(wf_df, pos, cost_bps=cost_bps)
bh = run_backtest(wf_df, buy_hold_positions(wf_df), cost_bps=cost_bps)
sma_pos = sma_crossover_positions(df).reindex(wf_df.index).fillna(0).astype(int)
sma = run_backtest(wf_df, sma_pos, cost_bps=cost_bps)
cls = classification_stats(proba, wf["labels"], threshold)

# ---- Today's signal ----
buy = p_today > threshold
nxt = d_today + pd.tseries.offsets.BDay(1)
signal_card(
    "Buy" if buy else "Hold cash", p_today, threshold, f"{nxt:%a %b %d}",
    f"The model gives {ticker} a {p_today:.0%} chance of closing higher over the next {LABEL_HORIZON} "
    f"trading days (data through {d_today:%b %d}) — {'above' if buy else 'below'} your "
    f"{threshold:.0%} threshold, so it would {'buy' if buy else 'stay in cash'}. "
    f"Historically it was right {cls['accuracy']:.0%} of the time here.",
)

# ---- Out-of-sample results ----
section(f"{ticker} · walk-forward out-of-sample", f"{wf_df.index[0]:%b %d, %Y} → {wf_df.index[-1]:%b %d, %Y}")
delta = model["total_return"] - bh["total_return"]
verdict(f"{'Beat' if delta >= 0 else 'Trailed'} buy & hold by {abs(delta):.1%} — every signal here was made "
        "by a model that never saw that day's data.", delta >= 0)
note("Hypothetical backtest. This stock exists today, so its past looks better than a random pick from back then "
     "would have (survivorship bias). Not financial advice.")
stat_grid([
    ("Strategy return", f"{model['total_return']:+.1%}", tone(model["total_return"])),
    ("Buy & hold", f"{bh['total_return']:+.1%}", ""),
    ("Sharpe", f"{model['sharpe_ratio']:.2f}", tone(model["sharpe_ratio"])),
    ("Max drawdown", f"{model['max_drawdown']:.1%}", "down"),
    ("Trades", f"{model['n_trades']}", ""),
])

section("Does the model add value?", "same window, same costs")
rows, tones = [], []
for name, r, p in (("Model (walk-forward)", model, pos), ("Buy & hold", bh, buy_hold_positions(wf_df)),
                   ("SMA 50/200 crossover", sma, sma_pos)):
    rows.append([name, f"{r['total_return']:+.1%}", f"{r['sharpe_ratio']:.2f}", f"{r['max_drawdown']:.1%}",
                 str(r["n_trades"]), f"{p.mean():.0%}"])
    tones.append(["", tone(r["total_return"]), "", "down", "", ""])
data_table(["Strategy", "Return", "Sharpe", "Max drawdown", "Trades", "Time in market"], rows, 0, tones)

# ---- Charts ----
head = st.columns([3, 1], vertical_alignment="bottom")
with head[0]:
    section("Price & signals", "hover a marker for its date, price and model confidence")
show_signals = head[1].toggle("Show signals", value=True, key="st_signals")
st.plotly_chart(price_chart(wf_df, pos, proba, show_signals), width="stretch", theme=None)

section("Equity curve", "growth of $1 · shaded panel = drawdown")
st.plotly_chart(equity_chart({"Strategy": model["cumulative_returns"], "Buy & hold": bh["cumulative_returns"],
                              "SMA 50/200": sma["cumulative_returns"]}), width="stretch", theme=None)

# ---- Diagnostics ----
section("Prediction quality", f"{cls['n']:,} out-of-sample days at threshold {threshold:.2f}")
d1, d2 = st.columns([1.2, 1], gap="medium")
with d1:
    stat_grid([
        ("Accuracy", f"{cls['accuracy']:.1%}", "accent"),
        ("Base rate (always 'up')", f"{cls['base_rate']:.1%}", ""),
        ("Precision", f"{cls['precision']:.1%}", ""),
        ("Recall", f"{cls['recall']:.1%}", ""),
    ])
    st.caption(f"Precision: when it said 'up', how often it was right. Recall: of the real up-moves, how many it "
               f"caught. Beat the base rate or the model isn't adding information. Brier score "
               f"{cls['brier']:.3f} (lower = better-calibrated probabilities; 0.25 = coin flip).")
with d2:
    confusion_matrix(cls["confusion"])

# ---- Downloads ----
changes = pos.diff().fillna(pos)
trades = pd.DataFrame({"action": changes[changes != 0].map({1: "BUY", -1: "SELL"}),
                       "close": wf_df.loc[changes != 0, "Close"].round(2),
                       "p_up": proba[changes != 0].round(4)})
equity = pd.DataFrame({"strategy": model["cumulative_returns"], "buy_hold": bh["cumulative_returns"],
                       "sma_50_200": sma["cumulative_returns"]}).round(5)
dl = st.columns(2)
dl[0].download_button("Download trades (CSV)", trades.to_csv(index_label="date"), f"{ticker}_trades.csv",
                      "text/csv", icon=":material/download:", width="stretch")
dl[1].download_button("Download equity curves (CSV)", equity.to_csv(index_label="date"), f"{ticker}_equity.csv",
                      "text/csv", icon=":material/download:", width="stretch")

with st.expander("In-sample results (training data — overfitting-prone)", icon=":material/warning:"):
    backend, train_df = in_sample(ticker, start, end)
    is_res = run_backtest(train_df, generate_signals(backend, train_df, threshold=threshold), cost_bps=cost_bps)
    st.caption(f"{train_df.index[0]:%b %d, %Y} → {train_df.index[-1]:%b %d, %Y} — the model saw this data, "
               "so these numbers flatter it. Compare with the out-of-sample results above.")
    stat_grid([("Strategy return", f"{is_res['total_return']:+.1%}", tone(is_res["total_return"])),
               ("Buy & hold", f"{is_res['buy_hold_return']:+.1%}", ""),
               ("Sharpe", f"{is_res['sharpe_ratio']:.2f}", tone(is_res["sharpe_ratio"]))])

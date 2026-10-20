"""Single-ticker backtest page: honest walk-forward results, baselines, robustness, today's signal."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from stock_ai.backtest.engine import run_backtest
from stock_ai.config import TICKER_SUGGESTIONS
from stock_ai.models.classifier import LABEL_HORIZON
from stock_ai.strategy.signal import generate_signals
from ui.components import (confusion_matrix, data_table, note, page_head, section, signal_card, skeleton_results,
                           stat_grid, tone, verdict_banner)
from ui_common import (COST_GRID_BPS, RANGES, SETTINGS, analyze, cost_sensitivity_chart, equity_chart, in_sample,
                       latest_trading_day, parse_tickers, persist, price_chart, range_start, valid_ticker)

COST_HELP = ("What you pay every time you buy or sell, in basis points. 1 bp = 0.01%, so 10 bps "
             "means 0.10% of each trade lost to commissions and slippage.")
THR_HELP = ("How sure the model must be before it buys. 0.50 = buy whenever it thinks 'up' is more "
            "likely than 'down'; 0.60 = only when it's at least 60% sure. Higher = fewer, pickier trades.")
CI_HELP = ("95% range for the Sharpe ratio from a block bootstrap (resampling 20-day runs of returns). "
           "If the range includes buy & hold's Sharpe, the difference is within noise.")
MAX_COMPARE = 4

ss = st.session_state
END = latest_trading_day()
persist("st_ticker", "st_compare", "st_range", "st_start", "st_end", "st_cost", "st_thr", "st_mode")

# Preload a ticker from Home (search box or a clicked card), once per arrival.
pre = ss.pop("preload_ticker", None) or st.query_params.get("ticker")
if pre and ss.get("_applied_preload") != pre:
    ss["_applied_preload"] = pre
    ss["st_ticker"] = pre.upper()
    ss.setdefault("st_end", END)
    ss.setdefault("st_start", range_start("Max", END))
    ss["st_run"] = (pre.upper(), ss["st_start"], ss["st_end"]) if valid_ticker(pre.upper()) else None
ss.setdefault("st_ticker", "AAPL")
ss.setdefault("st_compare", ["AAPL", "MSFT"])
ss.setdefault("st_range", "Max")
ss.setdefault("st_end", END)
ss.setdefault("st_start", range_start("Max", END))
persist("st_ticker", "st_compare", "st_range", "st_start", "st_end", "st_cost", "st_thr", "st_mode")   # save what a Home click preloaded


def _apply_range():
    if ss.get("st_range"):
        ss["st_start"] = range_start(ss["st_range"], ss["st_end"])


def _custom_dates():
    ss["st_range"] = None


page_head("Single Ticker", "Walk-forward backtest of one stock against simple baselines, plus today's model call.",
          eyebrow="Backtest")

with st.container(key="controls_single"):
    mode = st.segmented_control("Mode", ["Single", "Compare"], default="Single", key="st_mode",
                                help=f"Compare puts up to {MAX_COMPARE} tickers side by side.") or "Single"
    c = st.columns([1.3, 1.4, 1, 1])
    if mode == "Single":
        c[0].selectbox("Ticker", TICKER_SUGGESTIONS, key="st_ticker", accept_new_options=True,
                       help="Start typing for suggestions, or enter any US-listed symbol (e.g. BRK-B).")
    else:
        c[0].multiselect(f"Tickers (up to {MAX_COMPARE})", TICKER_SUGGESTIONS, key="st_compare",
                         default=["AAPL", "MSFT"], max_selections=MAX_COMPARE, accept_new_options=True)
    c[1].segmented_control("Range", list(RANGES), key="st_range", on_change=_apply_range)
    c[2].date_input("Data from", key="st_start", min_value=date(1990, 1, 1), max_value=END,
                    on_change=_custom_dates,
                    help="Where the model's training history starts. Results begin later, at the first "
                         "out-of-sample date shown below.")
    c[3].date_input("End", key="st_end", max_value=END, on_change=_custom_dates,
                    help=f"Defaults to the latest trading day ({END:%b %d, %Y}).")
    c2 = st.columns([1, 1, 0.7], vertical_alignment="bottom")
    cost_bps = c2[0].slider("Cost per trade (bps)", 0.0, 50.0, 10.0, 1.0, key="st_cost", help=COST_HELP)
    threshold = c2[1].slider("Confidence threshold", 0.50, 0.70, 0.50, 0.01, key="st_thr", help=THR_HELP)
    run = c2[2].button("Run backtest", icon=":material/play_arrow:", width="stretch")

if run:
    if ss["st_end"] - ss["st_start"] < timedelta(days=330):
        st.error("Pick a range of at least about a year — the model needs history to learn from.")
    elif mode == "Single":
        t = (ss["st_ticker"] or "").strip().upper()
        if not valid_ticker(t):
            st.error(f"“{ss['st_ticker']}” doesn't look like a ticker. Use letters like AAPL, MSFT or BRK-B.")
        else:
            ss["st_run"] = (t, ss["st_start"], ss["st_end"])
    else:
        ts = parse_tickers(",".join(ss.get("st_compare") or []))
        bad = [t for t in ts if not valid_ticker(t)]
        if bad:
            st.error(f"These don't look like tickers: {', '.join(bad)}.")
        elif len(ts) < 2:
            st.error("Pick at least two tickers to compare.")
        else:
            ss["st_cmp"] = (tuple(ts), ss["st_start"], ss["st_end"])


def _friendly(exc: Exception, ticker: str) -> str:
    msg = str(exc)
    if "No price data" in msg:
        return f"We couldn't find price data for **{ticker}**. Check the symbol (e.g. BRK-B, not BRK.B)."
    if isinstance(exc, ValueError):
        return SETTINGS.scrub(msg)
    return SETTINGS.scrub(f"Backtest failed for {ticker}: {type(exc).__name__}: {exc}")


def _ci(r: dict) -> str:
    lo, hi = r["sharpe_ci"]
    return "—" if lo != lo else f"{r['sharpe_ratio']:.2f}  [{lo:.2f}, {hi:.2f}]"


# =============================================================== compare mode ==
if mode == "Compare":
    if not ss.get("st_cmp"):
        st.info(f"Pick two to {MAX_COMPARE} tickers, then click **Run backtest**.")
        st.stop()
    tickers, start, end = ss["st_cmp"]
    holder = st.empty()
    holder.markdown(skeleton_results(), unsafe_allow_html=True)
    results, errors = {}, []
    for t in tickers:
        try:
            results[t] = analyze(t, start, end, threshold, cost_bps)
        except Exception as exc:  # noqa: BLE001 — one bad ticker shouldn't sink the comparison
            errors.append(_friendly(exc, t))
    holder.empty()
    for e in errors:
        st.error(e)
    if not results:
        st.stop()
    section("Compare · walk-forward out-of-sample", f"{len(results)} tickers · {cost_bps:.0f} bps per trade")
    rows, tones = [], []
    for t, a in results.items():
        m, bh = a["runs"]["Model (walk-forward)"][1], a["runs"]["Buy & hold"][1]
        e = a["edge"]
        nxt_state = "No edge" if not e["has_edge"] else ("Buy" if a["p_today"] > threshold else "Sell")
        rows.append([t, f"{m['total_return']:+.1%}", f"{bh['total_return']:+.1%}", _ci(m),
                     f"{e['brier']:.3f} vs {e['base_brier']:.3f}", "Yes" if e["has_edge"] else "No",
                     f"{nxt_state} ({a['p_today']:.0%})"])
        tones.append(["", tone(m["total_return"]), "", "", "", "up" if e["has_edge"] else "down", ""])
    data_table(["Ticker", "Model return", "Buy & hold", "Sharpe [95% CI]", "Brier vs base rate", "Edge?",
                "Today"], rows, None, tones)
    note("'Edge?' = the model's out-of-sample Brier score beats just quoting the stock's historical up-frequency. "
         "Where it says No, the app issues no Buy/Sell call.")
    section("Model equity curves", "growth of $1 · each ticker's own out-of-sample window")
    st.plotly_chart(equity_chart({t: a["runs"]["Model (walk-forward)"][1]["cumulative_returns"]
                                  for t, a in results.items()}), width="stretch", theme=None)
    st.stop()

# ================================================================ single mode ==
if not ss.get("st_run"):
    st.info("Pick a ticker and range, then click **Run backtest**. Works for any US-listed stock.")
    st.stop()

ticker, start, end = ss["st_run"]
if ((ss["st_ticker"] or "").strip().upper(), ss["st_start"], ss["st_end"]) != (ticker, start, end):
    note(f"Showing {ticker} {start:%b %Y}–{end:%b %Y}. Click Run backtest to apply your new ticker or dates.")

holder = st.empty()
holder.markdown(skeleton_results(), unsafe_allow_html=True)  # no blank flash while models train
view_key = (ticker, start, end)
try:
    a = analyze(ticker, start, end, threshold, cost_bps,
                view_from=ss.get("st_view") if ss.get("_view_key") == view_key else None)
except Exception as exc:  # noqa: BLE001
    holder.empty()
    st.error(_friendly(exc, ticker))
    st.stop()
holder.empty()

first_oos, edge = a["first_oos"], a["edge"]
if ss.get("_view_key") != view_key:
    ss["_view_key"], ss["st_view"] = view_key, first_oos
proba, wf_df, pos, cls = a["proba"], a["wf_df"], a["pos"], a["cls"]
model, bh = a["runs"]["Model (walk-forward)"][1], a["runs"]["Buy & hold"][1]
sma = a["runs"]["SMA 50/200 crossover"][1]

# ---- Today's signal (gated on model health) ----
p_today, adj = a["p_today"], a["p_today"] - a["hist_up"]
nxt = a["d_today"] + pd.tseries.offsets.BDay(1)
if not edge["has_edge"]:
    state = "none"
    expl = (f"No edge: the model has not reliably beaten the base rate on {ticker}. Its out-of-sample Brier score "
            f"({edge['brier']:.3f}) is not clearly better than just saying 'up' {edge['base_rate']:.0%} of the time "
            f"({edge['base_brier']:.3f}), so its {p_today:.0%} reading is not trustworthy enough to act on.")
else:
    state = "buy" if p_today > threshold else "sell"
    expl = (f"The model gives {ticker} a {p_today:.0%} chance of closing higher over the next {LABEL_HORIZON} "
            f"trading days (data through {a['d_today']:%b %d}); that is {adj:+.1%} versus the stock's usual "
            f"{a['hist_up']:.0%} up-frequency. {'Above' if state == 'buy' else 'Below'} your {threshold:.0%} "
            f"threshold, so it would {'buy' if state == 'buy' else 'exit / stay out'}.")
signal_card(state, p_today, adj, threshold, f"{nxt:%a %b %d}", expl)

# ---- Out-of-sample window (explicit) ----
section(f"{ticker} · walk-forward out-of-sample", f"{wf_df.index[0]:%b %d, %Y} → {wf_df.index[-1]:%b %d, %Y}")
if a["df"].attrs.get("market_regime_missing"):
    st.warning("SPY data didn't load, so the market-regime input is flat for this run. Results are still valid but "
               "slightly different from normal; try again in a few minutes.")
if wf_df.index[-1] < a["df"].index[-1]:
    st.caption(f"Results end {wf_df.index[-1]:%b %d, %Y}, not {a['df'].index[-1]:%b %d}: the last {LABEL_HORIZON} trading "
               f"days can't be graded yet because each prediction is judged on the {LABEL_HORIZON} days after it.")
v1, v2 = st.columns([1.2, 2.8], vertical_alignment="center")
v1.date_input("Results from", key="st_view", min_value=first_oos, max_value=(wf_df.index[-1] - timedelta(days=120)).date(),
              help="Defaults to the first out-of-sample date: the first day the model predicted without having "
                   "seen it. Moving it later only crops the results window.")
v2.caption(f"Model trained on {ss['st_start']:%b %d, %Y} → {first_oos:%b %d, %Y}; the **first out-of-sample date is "
           f"{first_oos:%b %d, %Y}**. Every number and chart below starts there — nothing is graded on data the "
           "model learned from.")

verdict_banner([
    ("Beat buy and hold?", model["total_return"] > bh["total_return"],
     f"{model['total_return']:+.0%} vs {bh['total_return']:+.0%}"),
    ("Beat the SMA crossover?", model["total_return"] > sma["total_return"],
     f"{model['total_return']:+.0%} vs {sma['total_return']:+.0%}"),
    ("Better calibrated than chance?", edge["has_edge"],
     f"Brier {edge['brier']:.3f} vs {edge['base_brier']:.3f} for the base rate"),
])
note("Hypothetical backtest. This stock exists today, so its past looks better than a random pick from back then "
     "would have (survivorship bias). It also assumes you trade at the same close that produced the signal; the live "
     "bot places orders after the close and they fill at the next open. Not financial advice.")
stat_grid([
    ("Strategy return", f"{model['total_return']:+.1%}", tone(model["total_return"])),
    ("Buy & hold", f"{bh['total_return']:+.1%}", ""),
    ("Sharpe", f"{model['sharpe_ratio']:.2f}", tone(model["sharpe_ratio"])),
    ("Max drawdown", f"{model['max_drawdown']:.1%}", "down"),
    ("Buys + sells", f"{model['n_trades']}", ""),
])

section("Does the model add value?", "same window, same costs · Sharpe shown with a 95% bootstrap range")
rows, tones = [], []
for name, (p, r) in a["runs"].items():
    rows.append([name, f"{r['total_return']:+.1%}", _ci(r), f"{r['max_drawdown']:.1%}", str(r["n_trades"]),
                 f"{p.mean():.0%}"])
    tones.append(["", tone(r["total_return"]), "", "down", "", ""])
data_table(["Strategy", "Return", "Sharpe [95% CI]", "Max drawdown", "Buys + sells", "Time in market"], rows, 0, tones)
st.caption(CI_HELP)

# ---- Charts ----
head = st.columns([3, 1], vertical_alignment="bottom")
with head[0]:
    section("Price & signals", "hover a marker for its date, price and model confidence")
show_signals = head[1].toggle("Show signals", value=True, key="st_signals")
st.plotly_chart(price_chart(wf_df, pos, proba, show_signals), width="stretch", theme=None)

section("Equity curve", "growth of $1 · shaded panel = drawdown")
st.plotly_chart(equity_chart({"Strategy": model["cumulative_returns"], "Buy & hold": bh["cumulative_returns"],
                              "SMA 50/200": sma["cumulative_returns"]}), width="stretch", theme=None)

section("Net of costs", f"strategy return at {', '.join(str(b) for b in COST_GRID_BPS)} bps per trade")
st.plotly_chart(cost_sensitivity_chart(a["sens"], bh["total_return"]), width="stretch", theme=None)
st.caption("If the bars fall below the dashed buy & hold line as costs rise, the edge is fragile. "
           f"Costs are charged on {model['n_trades']} buys and sells here. The buy & hold line pays the same {cost_bps:.0f} bps "
           "entry cost as the stats above.")

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
               f"caught. Brier score {edge['brier']:.3f} vs {edge['base_brier']:.3f} for always quoting the "
               f"historical up-frequency (lower = better; the model must beat the base rate to claim an edge).")
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

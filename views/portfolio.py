"""Multi-ticker cross-sectional portfolio page (walk-forward, vs. benchmarks)."""

import time as _time
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from stock_ai.backtest.multi_engine import combine_signals, run_multi_backtest
from stock_ai.config import PRESETS
from stock_ai.models.evaluation import classification_stats
from stock_ai.strategy.baselines import momentum_weights
from ui.components import data_table, note, page_head, section, stat_grid, tone, verdict
from ui_common import (RANGES, SETTINGS, contribution_chart, equity_chart, latest_trading_day,
                       parse_tickers, range_start, valid_ticker, walk_forward)

COST_HELP = ("What you pay every time you buy or sell, in basis points. 1 bp = 0.01%, so 10 bps "
             "means 0.10% of each trade lost to commissions and slippage.")
TOPN_HELP = "How many of the highest-ranked stocks to hold each day, split equally."

ss = st.session_state
END = latest_trading_day()
ss.setdefault("pf_preset", ss.pop("preload_preset", None) or "Mega-cap tech")
ss.setdefault("pf_range", "Max")
ss.setdefault("pf_end", END)
ss.setdefault("pf_start", range_start("Max", END))
ss.setdefault("pf_custom", "AAPL, MSFT, NVDA, JPM, XOM, KO")
if "preload_preset" in ss:
    ss["pf_preset"] = ss.pop("preload_preset")


def _apply_range():
    if ss.get("pf_range"):
        ss["pf_start"] = range_start(ss["pf_range"], ss["pf_end"])


def _custom_dates():
    ss["pf_range"] = None


page_head("Portfolio", "Rank a universe every day, hold the top N, and compare against equal-weight and momentum.",
          eyebrow="Universe")

with st.container(key="controls_portfolio"):
    c = st.columns([1.6, 1.5, 1, 1])
    c[0].segmented_control("Universe", [*PRESETS, "Custom"], key="pf_preset")
    c[1].segmented_control("Range", list(RANGES), key="pf_range", on_change=_apply_range)
    c[2].date_input("Start", key="pf_start", min_value=date(1990, 1, 1), max_value=END, on_change=_custom_dates)
    c[3].date_input("End", key="pf_end", max_value=END, on_change=_custom_dates)
    if ss.get("pf_preset") == "Custom":
        st.text_area("Tickers (comma or space separated)", key="pf_custom", height=68)
    else:
        st.caption("Holdings: " + ", ".join(PRESETS.get(ss.get("pf_preset") or "Mega-cap tech", [])))
    c2 = st.columns([1, 1, 0.7], vertical_alignment="bottom")
    top_n = c2[0].slider("Top-N held", 1, 15, 3, 1, key="pf_topn", help=TOPN_HELP)
    cost_bps = c2[1].slider("Cost per trade (bps)", 0.0, 50.0, 10.0, 1.0, key="pf_cost", help=COST_HELP)
    run = c2[2].button("Run backtest", icon=":material/play_arrow:", width="stretch")

if run:
    preset = ss.get("pf_preset") or "Mega-cap tech"
    tickers = parse_tickers(ss["pf_custom"]) if preset == "Custom" else list(PRESETS[preset])
    bad = [t for t in tickers if not valid_ticker(t)]
    if bad:
        st.error(f"These don't look like tickers: {', '.join(bad)}. Use symbols like AAPL or BRK-B.")
    elif len(tickers) < 2:
        st.error("Add at least two tickers to build a portfolio.")
    elif ss["pf_end"] - ss["pf_start"] < timedelta(days=330):
        st.error("Pick a range of at least about a year.")
    else:
        ss["pf_run"] = (tuple(tickers), ss["pf_start"], ss["pf_end"])

if not ss.get("pf_run"):
    st.info("Choose a universe and range, then click **Run backtest**.")
    st.stop()

tickers, start, end = ss["pf_run"]

# ---- Train (cached per ticker) with a real progress bar ----
proba_by, returns_by, labels_by, skipped = {}, {}, {}, []
bar = st.progress(0.0, text=f"Training 0/{len(tickers)} tickers…")
t0 = _time.time()
for i, t in enumerate(tickers, start=1):
    try:
        wf = walk_forward(t, start, end)
        from ui_common import load_prices  # noqa: PLC0415 — cached, cheap after first load
        df = load_prices(t, start, end)
        proba_by[t] = wf["proba"]
        returns_by[t] = df.loc[wf["proba"].index, "return_1d"]
        labels_by[t] = wf["labels"]
    except Exception:  # noqa: BLE001 — a bad/short ticker shouldn't sink the run
        skipped.append(t)
    elapsed = _time.time() - t0
    eta = elapsed / i * (len(tickers) - i)
    bar.progress(i / len(tickers), text=f"Training {i}/{len(tickers)} tickers… "
                 + (f"~{eta:.0f}s left" if eta > 1 else "almost done"))
bar.empty()

try:
    res, proba_m, returns_m = combine_signals(proba_by, returns_by, top_n, cost_bps)
except ValueError:
    st.error("None of these tickers had enough history in this range. Try a longer range.")
    st.stop()
mom = run_multi_backtest(returns_m, momentum_weights(returns_m, n=top_n), cost_bps=cost_bps)
pooled = classification_stats(pd.concat(proba_by.values()), pd.concat(labels_by.values()))

section("Portfolio · walk-forward out-of-sample",
        f"top-{top_n} of {len(proba_by)} · {res['n_days']:,} sessions · ~{res['avg_positions']:.1f} names/day")
delta = res["total_return"] - res["buy_hold_return"]
verdict(f"{'Beat' if delta >= 0 else 'Trailed'} the equal-weight benchmark by {abs(delta):.1%}.", delta >= 0)
note("Survivorship-biased: these are today's companies, so the past looks rosier than it was. "
     "Hypothetical results, not financial advice.")
if skipped:
    st.warning(f"Skipped (no usable data): {', '.join(skipped)}")
stat_grid([
    ("Portfolio return", f"{res['total_return']:+.1%}", tone(res["total_return"])),
    ("Equal-weight all", f"{res['buy_hold_return']:+.1%}", ""),
    ("Portfolio Sharpe", f"{res['portfolio_sharpe']:.2f}", tone(res["portfolio_sharpe"])),
    ("Max drawdown", f"{res['max_drawdown']:.1%}", "down"),
    ("Turnover / day", f"{res['turnover_daily']:.0%}", ""),
])
st.caption(f"Turnover = share of the portfolio traded per day (~{res['turnover_daily'] * 252:.0f}× per year). "
           f"Each trade costs {cost_bps:.0f} bps. Pooled prediction accuracy {pooled['accuracy']:.1%} vs "
           f"{pooled['base_rate']:.1%} base rate.")

section("Does the model add value?", "same universe, window and costs")
rows, tones = [], []
for name, r, sharpe in (("Model top-N", res, res["portfolio_sharpe"]),
                        ("Equal-weight all", {**res, "total_return": res["buy_hold_return"],
                                              "max_drawdown": float((res["benchmark_cumulative"] / res["benchmark_cumulative"].cummax() - 1).min()),
                                              "turnover_daily": 0.0}, res["benchmark_sharpe"]),
                        ("Momentum top-N (6-mo)", mom, mom["portfolio_sharpe"])):
    rows.append([name, f"{r['total_return']:+.1%}", f"{sharpe:.2f}", f"{r['max_drawdown']:.1%}",
                 f"{r['turnover_daily']:.0%}"])
    tones.append(["", tone(r["total_return"]), "", "down", ""])
data_table(["Strategy", "Return", "Sharpe", "Max drawdown", "Turnover / day"], rows, 0, tones)

section("Equity curve", "growth of $1 · shaded panel = model drawdown")
st.plotly_chart(equity_chart({"Model top-N": res["cumulative_returns"],
                              "Equal-weight all": res["benchmark_cumulative"],
                              "Momentum top-N": mom["cumulative_returns"]}), width="stretch", theme=None)

h1, h2 = st.columns([1, 1.3], gap="medium")
with h1:
    section("Current holdings", f"as of {proba_m.index[-1]:%b %d, %Y}")
    latest_w = res["weights"].iloc[-1]
    latest_p = proba_m.iloc[-1]
    held = latest_w[latest_w > 0].index
    data_table(["Ticker", "Weight", "Score (P up)"],
               [[t, f"{latest_w[t]:.0%}", f"{latest_p[t]:.0%}"] for t in sorted(held, key=lambda x: -latest_p[x])],
               highlight=None)
    st.caption("Next session's target holdings: the top-N by model score.")
with h2:
    section("Contribution by ticker", "summed daily contribution to return")
    st.plotly_chart(contribution_chart(res["contributions"]), width="stretch", theme=None)

equity = pd.DataFrame({"model_top_n": res["cumulative_returns"], "equal_weight": res["benchmark_cumulative"],
                       "momentum_top_n": mom["cumulative_returns"]}).round(5)
w = res["weights"]
trades = (w.diff().fillna(w).stack().loc[lambda s: s != 0].rename("weight_change").round(4).reset_index()
          .rename(columns={"level_0": "date", "level_1": "ticker"}))
dl = st.columns(2)
dl[0].download_button("Download equity curves (CSV)", equity.to_csv(index_label="date"), "portfolio_equity.csv",
                      "text/csv", icon=":material/download:", width="stretch")
dl[1].download_button("Download rebalances (CSV)", trades.to_csv(index=False), "portfolio_rebalances.csv",
                      "text/csv", icon=":material/download:", width="stretch")

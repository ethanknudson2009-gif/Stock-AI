"""News Radar: which stocks have the most positive/negative fresh news right now."""

from html import escape

import pandas as pd
import streamlit as st

from bot import REPO_ROOT
from stock_ai.config import PRESETS
from stock_ai.data.news import rank_tickers, top_headlines
from stock_ai.data.sentiment import llm_available
from stock_ai.execution.signal_log import live_accuracy, resolve_outcomes
from ui.components import banner, data_table, note, page_head, section, skeleton_results, stat_grid, tone
from ui_common import (SETTINGS, fmt_stamp, news_for, now_et, parse_tickers, recent_closes, valid_ticker,
                       watchlist_quotes)

PICK_LOG = REPO_ROOT / "logs" / "news_picks.csv"
LOOKBACKS = {"1 day": 1, "3 days": 3, "7 days": 7}
ss = st.session_state

page_head("News Radar", "Fresh headlines scored for tone, ranked by ticker. A research lead list — not a trade signal.",
          eyebrow="Live news")

with st.container(key="controls_news"):
    c = st.columns([1.6, 1.0, 1.0, 0.7], vertical_alignment="bottom")
    preset = c[0].segmented_control("Universe", [*PRESETS, "Custom"], default="Large-cap 30", key="nw_preset")
    window = c[1].segmented_control("Lookback", list(LOOKBACKS), default="3 days", key="nw_days")
    scoring = c[2].segmented_control("Scoring", ["Claude", "Word list"], default="Claude" if llm_available() else "Word list",
                                     key="nw_scoring", help="Claude reads each headline for meaning (costs a few cents, "
                                     "cached). The word list just counts positive/negative words.")
    if c[3].button("Refresh", icon=":material/refresh:", width="stretch"):
        news_for.clear()
        watchlist_quotes.clear()
    if preset == "Custom":
        st.text_area("Tickers (comma or space separated)", key="nw_custom", height=68,
                     value=ss.get("nw_custom", "AAPL, TSLA, NVDA, AMD, PLTR"))

universe = parse_tickers(ss.get("nw_custom", "")) if preset == "Custom" else list(PRESETS.get(preset or "Large-cap 30"))
bad = [t for t in universe if not valid_ticker(t)]
if bad or len(universe) < 1:
    st.error(f"These don't look like tickers: {', '.join(bad) or '(none entered)'}.")
    st.stop()
days = LOOKBACKS.get(window or "3 days", 3)

holder = st.empty()
holder.markdown(skeleton_results(), unsafe_allow_html=True)
try:
    news = news_for(tuple(universe), days, use_llm=(scoring == "Claude" and llm_available()))
except Exception as exc:  # noqa: BLE001
    holder.empty()
    st.error(SETTINGS.scrub(f"Could not load news: {type(exc).__name__}: {exc}"))
    st.stop()
if news.empty:
    holder.empty()
    st.info("No news in this window for these tickers. Try a longer lookback.")
    st.stop()

ranked = rank_tickers(news, universe)
quotes, _ = watchlist_quotes(tuple(universe))   # still behind the skeleton: this download is the slow part
holder.empty()
move = {q["ticker"]: q["pct"] for q in quotes}
last = {q["ticker"]: q["last"] for q in quotes}

stats = news.attrs.get("llm_stats") or {}
by_claude = int(news["sentiment_llm"].notna().sum()) if "sentiment_llm" in news else 0
if scoring == "Claude" and by_claude == 0:
    st.warning("Claude scoring is unavailable right now"
               + (f" ({stats['error']})" if stats.get("error") else " (no API key)") + " — showing word-list scores.")
how = ("Tested on 2 years of history (45k articles, 30 stocks), the simple word-list tone had no predictive power for "
       "next-week returns (correlation ≈ 0). Claude's reading is untested. ") + (f"Claude read {by_claude} of {len(news)} articles for meaning" if by_claude else
       "A simple finance-word list scored the headlines") + ", weighted by freshness. Nothing here is proven to " \
      "predict prices — the track record at the bottom measures it live."
banner("info", "How to read this", how, icon="info")
stat_grid([("Articles", f"{len(news):,}", ""), ("Tickers with news", f"{int((ranked['articles'] > 0).sum())}", ""),
           ("Updated", fmt_stamp(now_et()), "accent"), ("Window", window or "3 days", "")])
quiet = ranked.loc[ranked["articles"] == 0, "ticker"].tolist()
if quiet:
    st.caption(f"No news in this window for: {', '.join(quiet)}.")
if len(news) >= 600:
    st.warning("The news feed hit its 600-article limit, so the oldest articles in this window were cut off. "
               "Try a shorter lookback or a smaller universe.")

# ---- Top picks ----
bulls = ranked[(ranked["label"] == "Bullish")].head(3)
bears = ranked[(ranked["label"] == "Bearish")].sort_values("score").head(3)
b1, b2 = st.columns(2, gap="medium")
with b1:
    section("Most positive news", "candidates to research")
    stat_grid([(f"{r.ticker} · {r.articles} articles", f"{r.score + 0.0:+.2f}", "up") for r in bulls.itertuples()]
              or [("None", "no clearly bullish names", "")])
with b2:
    section("Most negative news", "names to be careful with")
    stat_grid([(f"{r.ticker} · {r.articles} articles", f"{r.score:+.2f}", "down") for r in bears.itertuples()]
              or [("None", "no clearly bearish names", "")])

# ---- Ranking table ----
section("Ranking", "score = recency-weighted tone, shrunk when coverage is thin")
shown = ranked[ranked["articles"] > 0]
data_table(["Ticker", "News tone", "Score", "Articles", "Today", "Price"],
           [[r.ticker, r.label, f"{r.score + 0.0:+.2f}" if abs(r.score) >= 0.005 else "0.00", str(r.articles),
             f"{move[r.ticker]:+.1f}%" if r.ticker in move else "—",
             f"${last[r.ticker]:,.2f}" if r.ticker in last else "—"] for r in shown.itertuples()],
           None, [["", tone(r.score), tone(r.score), "", tone(move.get(r.ticker, 0)), ""] for r in shown.itertuples()])

# ---- Headlines ----
section("Headlines", "newest first · click to read")
pick = st.selectbox("Ticker", shown["ticker"].tolist(), key="nw_pick", label_visibility="collapsed")
for _, a in top_headlines(news, pick, 10).iterrows():
    age = pd.Timestamp.now(tz="UTC") - a["time"]
    hrs = age.total_seconds() / 3600
    when = f"{hrs * 60:.0f}m ago" if hrs < 1 else f"{hrs:.0f}h ago" if hrs < 48 else f"{hrs / 24:.0f}d ago"
    tag = "up" if a["sentiment"] > 0.15 else "down" if a["sentiment"] < -0.15 else ""
    st.markdown(f'<div class="note"><span class="badge">{a["sentiment"]:+.1f}</span>&nbsp; '
                f'<a href="{escape(a["url"] or "#")}" target="_blank" rel="noopener">{escape(a["headline"])}</a> '
                f'<span style="opacity:.6">— {escape(a["source"] or "")} · {when}</span></div>', unsafe_allow_html=True)

# ---- Track record: the daily job logs the day's top-5 positive-news picks; this page only reads and grades them ----
section("Track record", "the daily job logs the top-5 positive-news picks and grades them 5 trading days later")
if PICK_LOG.exists():
    raw = pd.read_csv(PICK_LOG)
    log = resolve_outcomes(recent_closes(tuple(sorted(raw["ticker"].unique())), str(raw["date"].min())), PICK_LOG)
    acc = live_accuracy(log)
    stat_grid([("Picks logged", f"{len(log)}", ""), ("Graded", f"{acc['n']}", ""),
               ("Went up", f"{acc['accuracy']:.0%}" if acc["n"] else "—", "accent"),
               ("Market base rate", f"{acc['base_rate']:.0%}" if acc["n"] else "—", "")])
    note("A pick 'worked' if the stock closed higher 5 trading days later. Compare to the base rate: stocks "
         "rise about 55–59% of the time anyway, so only a clear, sustained gap over it would mean something.")
else:
    st.info("Picks are logged by the daily job after each market close; results appear once 5 trading days have passed.")

"""Paper-trade preview & confirm page (safe by default: DRY_RUN on)."""

import pandas as pd
import streamlit as st

import bot
from stock_ai.config import PRESETS
from stock_ai.execution.signal_log import live_accuracy, log_signals, resolve_outcomes
from ui.components import banner, data_table, note, page_head, section, stat_grid
from ui_common import SETTINGS, fmt_stamp, get_broker, has_edge, latest_prices, now_et, parse_tickers, recent_closes, valid_ticker

BACKTEST_ACC = 0.551   # 30-ticker harness median accuracy, measured 2026-10-16 -- re-run scripts/run_harness.py to refresh

ss = st.session_state
page_head("Paper Trade", "Preview today's intended orders, review them, then confirm.", eyebrow="Execution")

broker, broker_label = get_broker()
dry = bot.dry_run_enabled()
if dry:
    banner("warn", "DRY RUN is ON",
           "Orders are written to logs/orders.csv only — nothing is sent to any broker.", icon="shield")
else:
    banner("danger", "DRY RUN is OFF — live paper orders",
           "Confirming will submit real orders to your Alpaca paper account.", icon="warning")
stat_grid([
    ("Broker", "Alpaca paper" if broker_label.startswith("Alpaca") else "Demo (FakeBroker)", ""),
    ("Target invested", f"{bot.TARGET_INVESTED:.0%} of equity", "accent"),
    ("Max per position", f"{bot.MAX_POSITION_PCT:.0%} of equity", "accent"),
    ("Max per order", f"${bot.MAX_ORDER_USD:,.0f}", "accent"),
    ("Max orders / day", f"{bot.MAX_ORDERS_PER_DAY}", "accent"),
])
st.caption(broker_label)

# ---- Positions & P&L ----
section("Open positions & P&L", broker_label)
try:
    details = broker.get_position_details() if hasattr(broker, "get_position_details") else None
except Exception as exc:  # noqa: BLE001
    details = None
    st.warning(SETTINGS.scrub(f"Could not load positions: {type(exc).__name__}: {exc}"))
if details:
    data_table(["Ticker", "Qty", "Avg entry", "Last", "Value", "Unrealized P&L"],
               [[d["ticker"], f"{d['qty']:g}", f"${d['avg_entry']:,.2f}", f"${d['price']:,.2f}",
                 f"${d['value']:,.0f}", f"{d['pl']:+,.0f} ({d['pl_pct']:+.1%})"] for d in details],
               None, [["", "", "", "", "", "up" if d["pl"] >= 0 else "down"] for d in details])
    st.caption(f"Total unrealized P&L: {sum(d['pl'] for d in details):+,.2f} USD · live from Alpaca at {fmt_stamp(now_et())} "
               "(My Trades refreshes every minute, so the two can differ slightly)")
else:
    st.info("No open positions to show" + (" — connect Alpaca paper keys to see your real account."
            if broker_label.startswith("FakeBroker") else "."))

with st.container(key="controls_paper"):
    c = st.columns([1.6, 1], vertical_alignment="bottom")
    preset = c[0].segmented_control("Universe", [*PRESETS, "Custom"], default="Mega-cap tech", key="pt_preset")
    top_n = c[1].slider("Top-N to hold", 1, 15, 10, 1, key="pt_topn",
                        help="How many of the highest-ranked stocks the bot wants to own.")
    if preset == "Custom":
        st.text_area("Tickers (comma or space separated)", key="pt_custom", height=68,
                     value=ss.get("pt_custom", "AAPL, MSFT, NVDA"))
    preview = st.button("Preview orders", icon=":material/visibility:")

if preview:
    universe = parse_tickers(ss.get("pt_custom", "")) if preset == "Custom" else list(PRESETS.get(preset or "Mega-cap tech"))
    bad = [t for t in universe if not valid_ticker(t)]
    if bad:
        st.error(f"These don't look like tickers: {', '.join(bad)}.")
        st.stop()
    try:
        sigs: dict = {}
        risk_notes: list = []
        with st.spinner(f"Computing today's signals for {len(universe)} tickers…"):
            orders = bot.plan_orders(broker, universe=universe, top_n_count=top_n, signals_out=sigs, risk_out=risk_notes)
            bot.enforce_caps(orders)
        px = latest_prices(tuple(sigs))
        log_signals(sigs, px, bot.trading_day_today(), bot.SIGNAL_LOG)  # for live-vs-backtest tracking
    except Exception as exc:  # noqa: BLE001
        st.error(SETTINGS.scrub(f"Could not build orders: {type(exc).__name__}: {exc}"))
        st.stop()
    ss["pending_orders"] = orders
    ss["risk_notes"] = risk_notes
    ss.pop("pt_ack", None)

def _signal_log_section():
    section("Signal log · live vs backtest", "every previewed signal, graded 5 trading days later")
    if not bot.SIGNAL_LOG.exists():
        st.info("No signals logged yet. Each **Preview orders** records the model's P(up) per ticker here.")
        return
    raw = pd.read_csv(bot.SIGNAL_LOG)
    closes = recent_closes(tuple(sorted(raw["ticker"].unique())), str(raw["date"].min()))
    log = resolve_outcomes(closes, bot.SIGNAL_LOG)
    acc = live_accuracy(log)
    stat_grid([("Signals logged", f"{len(log)}", ""), ("Graded so far", f"{acc['n']}", ""),
               ("Live accuracy", f"{acc['accuracy']:.1%}" if acc["n"] else "—", "accent"),
               ("Backtest accuracy", f"{BACKTEST_ACC:.1%}", "")])
    st.caption("Live accuracy needs many graded signals before it means anything; with few, it is mostly luck. "
               + (f"Of those graded, {acc['base_rate']:.0%} went up (the base rate)." if acc["n"] else
                  f"{acc['pending']} signals are still waiting for their 5-day outcome."))
    shown = log.sort_values("date", ascending=False).head(30)
    data_table(["Date", "Ticker", "P(up)", "Price", "Outcome", "Went up?"],
               [[r["date"], r["ticker"], f"{r['p_up']:.0%}", f"${r['price']:,.2f}" if pd.notna(r["price"]) else "—",
                 f"${r['outcome_price']:,.2f}" if pd.notna(r["outcome_price"]) else "pending",
                 "—" if pd.isna(r["went_up"]) else ("Yes" if r["went_up"] else "No")] for _, r in shown.iterrows()],
               None, [["", "", "", "", "", "up" if r["went_up"] == 1 else ("down" if r["went_up"] == 0 else "")]
                      for _, r in shown.iterrows()])


if "pending_orders" not in ss:
    st.info("Choose a universe and click **Preview orders**. Nothing is sent at this step.")
    _signal_log_section()
    st.stop()

orders = ss.get("pending_orders") or []
if not orders:
    st.success("No changes needed — target holdings already match current positions.")
    _signal_log_section()
    st.stop()

for n in ss.get("risk_notes") or []:
    banner("warn", "Risk rule applied", n, icon="shield")

# ---- Step 1: review ----
section(f"Step 1 · Review {len(orders)} orders", f"for {bot.trading_day_today():%a %b %d, %Y}")
prices = latest_prices(tuple(sorted({o.ticker for o in orders})))
rows, tones, total = [], [], 0.0
for o in orders:
    px = prices.get(o.ticker)
    if o.side == "buy":
        dollars = o.notional or 0.0
        shares = f"~{dollars / px:.2f}" if px else "—"
    else:
        shares = f"{o.qty:g}" if o.qty else "all"
        dollars = (o.qty or 0) * px if px else 0.0
    total += dollars
    edge = has_edge(o.ticker) if o.side == "buy" else None
    rows.append([o.ticker, o.side.upper(), shares, f"${px:,.2f}" if px else "—", f"${dollars:,.0f}",
                 "—" if edge is None else ("Yes" if edge else "No edge")])
    tones.append(["", "up" if o.side == "buy" else "down", "", "", "", "down" if edge is False else ""])
data_table(["Ticker", "Side", "Shares (est.)", "Last price", "Est. dollars", "Model edge?"], rows, None, tones)
if any(r[5] == "No edge" for r in rows):
    banner("warn", "Some buys have no proven model edge",
           "For the tickers marked 'No edge' the model has not beaten the base rate out of sample. "
           "Treat these as a plumbing test, not a recommendation.", icon="info")
note(f"Estimated gross {total:,.0f} USD. Share counts are estimates from the latest close; fills will differ.")

# ---- Step 2: confirm ----
section("Step 2 · Confirm")
ack = st.checkbox("I've reviewed these orders" + ("" if dry else " and understand they will be sent"),
                  key="pt_ack")
if st.button("Confirm & submit", type="primary", icon=":material/send:", disabled=not ack):
    try:
        result = bot.submit_orders(broker, orders)  # submits exactly what was previewed
    except Exception as exc:  # noqa: BLE001
        st.error(SETTINGS.scrub(f"Submit failed: {type(exc).__name__}: {exc}"))
        st.stop()
    if result["status"] == "dry_run":
        st.success(f"DRY RUN: logged {result['planned']} orders to logs/orders.csv — none sent.")
    elif result["status"] == "halted":
        st.error(f"Halted: {result['reason']}.")
    elif result["status"] == "partial":
        st.warning(f"Submitted {result['submitted']} orders; {len(result['failed'])} failed: "
                   + "; ".join(SETTINGS.scrub(f"{t}: {m}") for t, m in result["failed"]))
    else:
        st.success(f"Submitted {result['submitted']} paper orders.")
    ss.pop("pending_orders", None)

_signal_log_section()

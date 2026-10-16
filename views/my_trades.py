"""My Trades: the live Alpaca paper account reflected inside the app (orders, positions, P&L, equity)."""

import re

import pandas as pd
import streamlit as st

from bot import SIGNAL_LOG
from ui.components import banner, data_table, note, page_head, section, stat_grid, tone
from ui_common import ET, account_snapshot, equity_history_chart, fmt_stamp

BOT_ID = re.compile(r"^\d{4}-\d{2}-\d{2}_[A-Z.\-]+_(buy|sell)$")
STATUS = {"accepted": "Queued", "new": "Queued", "pending_new": "Queued", "held": "Queued", "filled": "Filled",
          "partially_filled": "Partly filled", "canceled": "Canceled", "expired": "Expired", "rejected": "Rejected"}

page_head("My Trades", "Your Alpaca paper account, mirrored here: what we bought, what it's worth, what's waiting to fill.",
          eyebrow="Live paper account")
if st.button("Refresh", icon=":material/refresh:"):
    account_snapshot.clear()

snap = account_snapshot()
if snap is None:
    banner("warn", "Alpaca isn't connected", "Add ALPACA_API_KEY and ALPACA_SECRET_KEY to .env to see your account here.",
           icon="link_off")
    st.stop()

acct, positions, orders = snap["account"], snap["positions"], snap["orders"]
queued = [o for o in orders if STATUS.get(o["status"]) in ("Queued", "Partly filled")]
unreal = sum(p["pl"] for p in positions)
stat_grid([
    ("Account value", f"${acct['equity']:,.2f}", "accent"),
    ("Cash", f"${acct['cash']:,.2f}", ""),
    (f"Today ({acct['day_pl_pct']:+.2%})", f"{acct['day_pl']:+,.2f}", tone(acct["day_pl"])),
    ("Open P&L", f"{unreal:+,.2f}", tone(unreal)),
    ("Waiting to fill", f"{len(queued)}", ""),
])
st.caption(f"Updated {fmt_stamp(snap['fetched'])} · paper money only · starting balance $100,000")

# ---- Positions ----
section("Positions", "what we hold right now")
if positions:
    cost = sum(p["avg_entry"] * p["qty"] for p in positions)
    data_table(["Ticker", "Shares", "Avg entry", "Last", "Value", "P&L", "P&L %"],
               [[p["ticker"], f"{p['qty']:g}", f"${p['avg_entry']:,.2f}", f"${p['price']:,.2f}", f"${p['value']:,.0f}",
                 f"{p['pl']:+,.2f}", f"{p['pl_pct']:+.1%}"] for p in positions],
               None, [["", "", "", "", "", tone(p["pl"]), tone(p["pl"])] for p in positions])
    st.caption(f"Invested ${cost:,.0f} · unrealized {unreal:+,.2f} USD")
elif queued:
    st.info(f"No positions yet — {len(queued)} orders are accepted and queued. They fill when the market opens "
            "(9:30 AM ET on the next trading day); positions will appear here automatically.")
else:
    st.info("No positions and nothing queued. Place orders from the Paper Trade page.")

# ---- Orders ----
section("Orders", "newest first · Bot = placed by this app, Manual = placed on Alpaca directly")
sig = pd.read_csv(SIGNAL_LOG, dtype={"date": str}) if SIGNAL_LOG.exists() else pd.DataFrame(columns=["date", "ticker", "p_up"])
p_up = {(r.date, r.ticker): r.p_up for r in sig.itertuples()}
if orders:
    rows, tones = [], []
    for o in orders:
        when = o["submitted_at"].astimezone(ET)
        size = f"${o['notional']:,.0f}" if o["notional"] else f"{o['qty']:g} sh" if o["qty"] else "—"
        fill = f"${o['avg_price']:,.2f}" if o["avg_price"] else "—"
        bot = bool(BOT_ID.match(o["id"] or ""))
        p = p_up.get((when.strftime("%Y-%m-%d"), o["ticker"]))
        status = STATUS.get(o["status"], o["status"].replace("_", " ").title())
        rows.append([f"{when:%b %d %-I:%M %p}", o["ticker"], o["side"].upper(), size, status, fill,
                     "Bot" if bot else "Manual", f"{p:.0%}" if p is not None and bot else "—"])
        tones.append(["", "", "up" if o["side"] == "buy" else "down", "",
                      "up" if status == "Filled" else "down" if status in ("Rejected", "Canceled") else "", "", "", ""])
    data_table(["Placed (ET)", "Ticker", "Side", "Size", "Status", "Fill price", "Source", "Model P(up)"],
               rows, None, tones)
else:
    st.info("No orders yet.")

# ---- Equity ----
section("Account value over time", "daily, from Alpaca")
if len(snap["equity"]) >= 2:
    st.plotly_chart(equity_history_chart(snap["equity"]), width="stretch", theme=None)
else:
    st.info("The chart starts drawing once there are at least two trading days of history.")
note("Orders submitted after the close wait for the next open. Market orders fill at the open price, which can "
     "differ from the last close. Paper fills are simulated and are kinder than real ones.")

"""My Trades: the live Alpaca paper account reflected inside the app (orders, positions, P&L, equity)."""

import re
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from bot import DAILY_LOSS_LIMIT, MAX_PER_SECTOR, SIGNAL_LOG, STOP_LOSS_PCT
from stock_ai.config import SECTORS
from ui.components import banner, data_table, note, page_head, section, stat_grid, tone, verdict_banner
from ui_common import ET, account_snapshot, equity_history_chart, fmt_stamp, order_signal_day, spy_since

BOT_ID = re.compile(r"^\d{4}-\d{2}-\d{2}_[A-Z.\-]+_(buy|sell)$")
STATUS = {"accepted": "Queued", "new": "Queued", "pending_new": "Queued", "held": "Queued", "filled": "Filled",
          "partially_filled": "Partly filled", "canceled": "Canceled", "expired": "Expired", "rejected": "Rejected"}

page_head("My Trades", "Your Alpaca paper account, mirrored here: what we bought, what it's worth, what's waiting to fill.",
          eyebrow="Live paper account")
if st.button("Refresh", icon=":material/refresh:"):
    account_snapshot.clear()

snap = account_snapshot()
if snap and "error" in snap:
    banner("danger", "Couldn't reach Alpaca", snap["error"] + " — try Refresh in a moment.", icon="warning")
    st.stop()
if snap is None:
    banner("warn", "Alpaca isn't connected", "Add ALPACA_API_KEY and ALPACA_SECRET_KEY to .env to see your account here.",
           icon="link_off")
    st.stop()

acct, positions, orders = snap["account"], snap["positions"], snap["orders"]
bot_orders = [o for o in orders if BOT_ID.match(o["id"] or "")]
bot_tickers = {o["ticker"] for o in bot_orders}
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

# ---- Scoreboard vs SPY ----
section("Scoreboard", "is the bot beating just buying SPY?")
eq = snap["equity"]
fills = [o["filled_at"] for o in orders if o["filled_at"] is not None]
if not fills:
    st.info("The scoreboard starts once our first orders fill (next market open). Until then the account is all "
            "cash, and comparing it to SPY would be meaningless.")
else:
    first_fill = min(fills).astimezone(ET).date()
    before = [(t, e) for t, e in eq if datetime.fromtimestamp(t, timezone.utc).date() < first_fill]
    base = before[-1][1] if before else eq[0][1]
    spy = spy_since(first_fill)
    spy_before = spy[spy.index < pd.Timestamp(first_fill)]
    spy_base = float(spy_before.iloc[-1]) if len(spy_before) else float(spy.iloc[0])
    acct_ret, spy_ret = acct["equity"] / base - 1, float(spy.iloc[-1]) / spy_base - 1
    invested = 1 - acct["cash"] / acct["equity"]
    items = [("Whole account ahead of SPY?", acct_ret > spy_ret, f"account {acct_ret:+.2%} vs SPY {spy_ret:+.2%} (includes idle cash and your manual trades)")]
    bot_pos = [p for p in positions if p["ticker"] in bot_tickers]
    if bot_pos:
        # Match each position with the same dollars put into SPY on the day that position was first bought.
        entry = {}
        for o in bot_orders:
            if o["side"] == "buy" and o["filled_at"] is not None:
                d = o["filled_at"].astimezone(ET).date()
                entry[o["ticker"]] = min(d, entry.get(o["ticker"], d))
        cost = spy_gain = 0.0
        for p in bot_pos:
            d0 = entry.get(p["ticker"], first_fill)
            sp = spy_since(d0)
            before_d0 = sp[sp.index < pd.Timestamp(d0)]
            sp_base = float(before_d0.iloc[-1]) if len(before_d0) else float(sp.iloc[0])
            c = p["avg_entry"] * p["qty"]
            cost += c
            spy_gain += c * (float(sp.iloc[-1]) / sp_base - 1)
        bot_ret, bot_spy = sum(p["pl"] for p in bot_pos) / cost, spy_gain / cost
        items.append(("Bot positions beating the same dollars in SPY?", bot_ret > bot_spy,
                      f"bot positions {bot_ret:+.2%} vs SPY {bot_spy:+.2%}, each measured from its own buy date"))
    items.append(("Account mostly invested?", invested > 0.5, f"{invested:.0%} of the account is invested"))
    verdict_banner(items)
    st.caption(f"Since {first_fill:%b %d, %Y}: account {acct_ret:+.2%} (from \\${base:,.0f}) vs SPY {spy_ret:+.2%}. "
               "With only a few \\$500 positions most of the account sits in cash, so it can't move much either "
               "way; the bot-positions line is the fairer test. It covers positions still held, so anything already "
               "sold isn't counted yet. Prices here come from Alpaca and Yahoo, a minute or two apart.")

# ---- Risk rules ----
section("Risk rules", "limits the bot enforces on every run")
held = {}
for p in positions:
    held.setdefault(SECTORS.get(p["ticker"], "Not bot-managed"), []).append(p["ticker"])
worst = min((p["pl_pct"] for p in positions), default=0.0)
stat_grid([(f"Daily loss limit", f"-{DAILY_LOSS_LIMIT:.0%}", "accent"), ("Today", f"{acct['day_pl_pct']:+.2%}", tone(acct["day_pl_pct"])),
           ("Stop-loss per position", f"-{STOP_LOSS_PCT:.0%}", "accent"), ("Worst position", f"{worst:+.1%}", tone(worst)),
           ("Max per sector", f"{MAX_PER_SECTOR}", "accent")])
st.caption("Sectors held: " + (" · ".join(f"{k}: {', '.join(v)}" for k, v in sorted(held.items())) or "none yet")
           + ". If today's loss hits the limit, new buys pause; a position down past the stop is sold; a sector over "
           "the cap is skipped in favour of the next-best pick.")

# ---- Positions ----
section("Positions", "Bot = bought by the daily job · Manual = yours (the bot never sells these)")
if positions:
    cost = sum(p["avg_entry"] * p["qty"] for p in positions)
    data_table(["Ticker", "Source", "Shares", "Avg entry", "Last", "Value", "P&L", "P&L %"],
               [[p["ticker"], "Bot" if p["ticker"] in bot_tickers else "Manual", f"{p['qty']:g}", f"${p['avg_entry']:,.2f}",
                 f"${p['price']:,.2f}", f"${p['value']:,.0f}", f"{p['pl']:+,.2f}", f"{p['pl_pct']:+.1%}"] for p in positions],
               None, [["", "", "", "", "", "", tone(p["pl"]), tone(p["pl"])] for p in positions])
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
        # Alpaca stamps after-hours orders with the next session's time; the signal's own date is in the order id
        sig_day = order_signal_day(o["id"], when, bot)
        p = p_up.get((sig_day, o["ticker"]))
        status = STATUS.get(o["status"], o["status"].replace("_", " ").title())
        rows.append([f"{when:%b %d %-I:%M %p}", o["ticker"], o["side"].upper(), size, status, fill,
                     "Bot" if bot else "Manual", f"{p:.0%}" if p is not None and bot else "—"])
        tones.append(["", "", "up" if o["side"] == "buy" else "down", "",
                      "up" if status == "Filled" else "down" if status in ("Rejected", "Canceled") else "", "", "", ""])
    data_table(["Accepted (ET)", "Ticker", "Side", "Size", "Status", "Fill price", "Source", "Model P(up)"],
               rows, None, tones)
else:
    st.info("No orders yet.")

# ---- Equity ----
section("Account value over time", "daily, from Alpaca")
if len(snap["equity"]) >= 2:
    st.plotly_chart(equity_history_chart(snap["equity"], acct["equity"]), width="stretch", theme=None)
else:
    st.info("The chart starts drawing once there are at least two trading days of history.")
note("Orders submitted after the close wait for the next open. Market orders fill at the open price, which can "
     "differ from the last close. Paper fills are simulated and are kinder than real ones.")

"""Paper-trade preview & confirm page (safe by default: DRY_RUN on)."""

import streamlit as st

import bot
from stock_ai.config import PRESETS
from ui.components import banner, data_table, note, page_head, section, stat_grid
from ui_common import SETTINGS, get_broker, latest_prices, parse_tickers, valid_ticker

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
    ("Max per order", f"${bot.MAX_ORDER_USD:,.0f}", "accent"),
    ("Max orders / day", f"{bot.MAX_ORDERS_PER_DAY}", "accent"),
])
st.caption(broker_label)

with st.container(key="controls_paper"):
    c = st.columns([1.6, 1], vertical_alignment="bottom")
    preset = c[0].segmented_control("Universe", [*PRESETS, "Custom"], default="Mega-cap tech", key="pt_preset")
    top_n = c[1].slider("Top-N to hold", 1, 15, 5, 1, key="pt_topn",
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
        with st.spinner(f"Computing today's signals for {len(universe)} tickers…"):
            orders = bot.plan_orders(broker, universe=universe, top_n_count=top_n)
            bot.enforce_caps(orders)
    except Exception as exc:  # noqa: BLE001
        st.error(SETTINGS.scrub(f"Could not build orders: {type(exc).__name__}: {exc}"))
        st.stop()
    ss["pending_orders"] = orders
    ss.pop("pt_ack", None)

if "pending_orders" not in ss:
    st.info("Choose a universe and click **Preview orders**. Nothing is sent at this step.")
    st.stop()

orders = ss.get("pending_orders") or []
if not orders:
    st.success("No changes needed — target holdings already match current positions.")
    st.stop()

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
    rows.append([o.ticker, o.side.upper(), shares, f"${px:,.2f}" if px else "—", f"${dollars:,.0f}"])
    tones.append(["", "up" if o.side == "buy" else "down", "", "", ""])
data_table(["Ticker", "Side", "Shares (est.)", "Last price", "Est. dollars"], rows, None, tones)
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
    else:
        st.success(f"Submitted {result['submitted']} paper orders.")
    ss.pop("pending_orders", None)

"""Paper-trade preview & confirm page (safe by default: DRY_RUN on)."""

import streamlit as st

import bot
from stock_ai.config import DEFAULT_UNIVERSE
from ui_common import SETTINGS, get_broker, hero, inject_css

st.set_page_config(page_title="Paper Trade · Stock AI", page_icon="🧾", layout="wide")
inject_css()
hero('🧾 Paper <span class="accent">Trade</span>',
     "Preview today's intended orders, then confirm. Safe by default — nothing is sent unless you turn DRY_RUN off.")

with st.sidebar:
    st.header("Settings")
    with st.form("paper"):
        tickers_raw = st.text_area(
            "Universe (comma-separated — blank = Default Universe)", value="",
            help=f"Default Universe = {len(DEFAULT_UNIVERSE)} large-cap US stocks.")
        top_n = st.slider("Top-N to hold", 1, 15, 5, 1)
        submitted = st.form_submit_button("Preview orders", width="stretch")

broker, broker_label = get_broker()
dry = bot.dry_run_enabled()
st.caption(f"Broker: {broker_label}")
(st.info if dry else st.warning)(
    "DRY_RUN is ON — orders are logged, never sent." if dry
    else "DRY_RUN is OFF — confirming places real paper orders.")

if not submitted and "pending_orders" not in st.session_state:
    st.info("Choose your universe in the sidebar and click **Preview orders**.")
    st.stop()

if submitted:
    universe = [t.strip().upper() for t in tickers_raw.replace("\n", ",").split(",") if t.strip()] \
        or list(DEFAULT_UNIVERSE)
    try:
        with st.spinner(f"Computing today's signals for {len(universe)} tickers…"):
            orders = bot.plan_orders(broker, universe=universe, top_n_count=top_n)
            bot.enforce_caps(orders)
    except Exception as exc:  # noqa: BLE001
        st.error(SETTINGS.scrub(f"Could not build orders: {type(exc).__name__}: {exc}"))
        st.stop()
    st.session_state["pending_orders"] = orders

orders = st.session_state.get("pending_orders") or []
if not orders:
    st.success("No changes needed — target holdings already match current positions.")
    st.stop()

st.subheader(f"{len(orders)} intended orders for {bot.trading_day_today()}")
st.table([{"ticker": o.ticker, "side": o.side, "notional": o.notional, "qty": o.qty} for o in orders])

if st.button("Confirm & submit", type="primary"):
    try:
        result = bot.submit_orders(broker, orders)  # submits exactly what was previewed
    except Exception as exc:  # noqa: BLE001
        st.error(SETTINGS.scrub(f"Submit failed: {type(exc).__name__}: {exc}"))
        st.stop()
    if result["status"] == "dry_run":
        st.success(f"DRY_RUN: logged {result['planned']} orders to logs/orders.csv — none sent.")
    elif result["status"] == "halted":
        st.error(f"Halted: {result['reason']}.")
    else:
        st.success(f"Submitted {result['submitted']} paper orders.")
    st.session_state.pop("pending_orders", None)

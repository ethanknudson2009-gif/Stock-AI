"""Earnings strategy: hold the 20 stocks Jev likes best going INTO their report, sell them once they have reported.

Pure planning (no network): takes the scan's ranked rows plus the account and returns orders. Rules:
  * a NEW position needs a report that lands after tomorrow's open (a stock reporting before then has already moved
    by the time our order fills, so buying it is pointless);
  * a HELD position stays while its report is still ahead and it is still in Jev's top N, and is sold otherwise;
  * only names Jev leans UP on (score > 0) are bought; fewer than N is fine -- the rest stays in cash;
  * sizing is from account equity, never margin, with a per-name cap (earnings gaps are violent).
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from stock_ai.execution.base import Order, make_client_order_id
from stock_ai.execution.risk import daily_loss_halt, stop_loss_tickers

ET = ZoneInfo("America/New_York")
TOP_N = 20
TARGET_INVESTED = 0.75     # share of equity to have in positions
MAX_NAME_PCT = 0.10        # no name above this share of equity (an earnings gap can be +-10%)
REBALANCE_BAND = 0.30
CASH_BUFFER = 0.95
STOP_LOSS_PCT = 0.10
DAILY_LOSS_LIMIT = 0.03


def next_open(now: datetime) -> datetime:
    """9:30 ET on the next weekday after `now` (holidays are not modelled; a holiday only makes us slightly early)."""
    d = now.astimezone(ET).date() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return datetime.combine(d, time(9, 30), ET)


def choose_targets(rows: list[dict], held: set[str], now: datetime, top_n: int = TOP_N) -> list[str]:
    """Tickers to hold after tonight. `rows` = scan results (each with ticker, report_ts, score)."""
    opening = next_open(now)
    ok = []
    for r in rows:
        ts = datetime.fromisoformat(r["report_ts"])
        if ts <= now or r["score"] <= 0:
            continue                                    # already reported (sell) or Jev doesn't lean up
        if r["ticker"] in held or ts > opening:         # held names stay; new buys must report after tomorrow's open
            ok.append(r)
    ok.sort(key=lambda r: -r["score"])
    return [r["ticker"] for r in ok[:top_n]]


def plan(rows: list[dict], details: list[dict], equity: float, cash: float, day, now: datetime,
         day_pl_pct: float | None = None, notes: list | None = None, stopped_out: list | None = None,
         cooling: set | None = None, universe: set | None = None, top_n: int = TOP_N,
         extra_sells: tuple = ()) -> list[Order]:
    notes = notes if notes is not None else []
    managed = [d for d in details if universe is None or d["ticker"] in universe]
    held = {d["ticker"] for d in managed}
    values = {d["ticker"]: d["value"] for d in managed}
    prices = {d["ticker"]: d["price"] for d in managed}
    qty = {d["ticker"]: d["qty"] for d in managed}

    stopped = stop_loss_tickers(managed, STOP_LOSS_PCT)
    if stopped:
        notes.append(f"Stop-loss: {', '.join(stopped)} down {STOP_LOSS_PCT:.0%}+ from cost -- sell, no re-buy for a week.")
        if stopped_out is not None:
            stopped_out.extend(stopped)
    blocked = set(stopped) | (cooling or set())
    target = [t for t in choose_targets(rows, held - blocked, now, top_n) if t not in blocked]

    orders: list[Order] = [Order(t, "sell", make_client_order_id(day, t, "sell"), qty=qty[t])
                           for t in sorted(held) if t not in target]
    per = min(equity * TARGET_INVESTED / max(len(target), 1), equity * MAX_NAME_PCT) if equity > 0 else 0.0
    buys = []
    for t in target:
        v = values.get(t)
        if v is None:
            buys.append(Order(t, "buy", make_client_order_id(day, t, "buy"), notional=round(per, 2)))
        elif v < per * (1 - REBALANCE_BAND):
            buys.append(Order(t, "buy", make_client_order_id(day, t, "buy"), notional=round(per - v, 2)))
        elif v > per * (1 + REBALANCE_BAND) and prices.get(t, 0) > 0:
            orders.append(Order(t, "sell", make_client_order_id(day, t, "sell"), qty=round((v - per) / prices[t], 6)))
    for d in details:   # one-off liquidations the user asked for (e.g. a manual SPY); their proceeds count as cash
        if d["ticker"] in extra_sells and d["ticker"] not in held:
            orders.append(Order(d["ticker"], "sell", make_client_order_id(day, d["ticker"], "sell"), qty=d["qty"]))
            values[d["ticker"]], qty[d["ticker"]] = d["value"], d["qty"]
    need = sum(o.notional for o in buys)
    room = cash * CASH_BUFFER + sum(values.get(o.ticker, 0.0) if o.qty is None or o.qty == qty.get(o.ticker)
                                    else o.qty * prices.get(o.ticker, 0.0) for o in orders)
    if need > 0 and need > room:
        scale = max(room, 0.0) / need
        buys = [Order(o.ticker, "buy", o.client_order_id, notional=round(o.notional * scale, 2)) for o in buys]
        buys = [o for o in buys if o.notional >= 1]
        notes.append(f"Buys scaled to {scale:.0%} so the bot stays within the cash it actually has (no margin).")
    if daily_loss_halt(day_pl_pct, DAILY_LOSS_LIMIT):
        notes.append(f"Daily loss limit hit (account {day_pl_pct:+.1%} today): new buys paused.")
        buys = []
    return orders + buys

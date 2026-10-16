"""End-of-day paper-trading bot loop.

This module is PURE: only definitions and constants at import time — importing
`bot` never touches the network or submits an order (Pitfall #20). Trading runs
only when a function here is called explicitly.

Safety rails: DRY_RUN defaults ON (orders are logged, never sent, unless DRY_RUN
is explicitly false), a KILL_SWITCH file at the repo root halts submission, and
hard caps bound per-order dollars and daily order count (Pitfall #8).
"""

import csv
import os
from datetime import date
from pathlib import Path

from stock_ai.config import DEFAULT_UNIVERSE, SECTORS
from stock_ai.data.loader import fetch_price_history
from stock_ai.execution.base import Order, make_client_order_id
from stock_ai.execution.clock import trading_day_today
from stock_ai.execution.diff import diff
from stock_ai.execution.risk import apply_sector_cap, daily_loss_halt, stop_loss_tickers
from stock_ai.features.indicators import add_features
from stock_ai.models.classifier import FEATURE_COLUMNS, train_model
from stock_ai.models.rf_backend import RandomForestBackend

REPO_ROOT = Path(__file__).resolve().parent
KILL_SWITCH = REPO_ROOT / "KILL_SWITCH"
ORDER_LOG = REPO_ROOT / "logs" / "orders.csv"
SIGNAL_LOG = REPO_ROOT / "logs" / "signals.csv"

MAX_ORDER_USD = 500.0      # hard per-order dollar cap (BL-02)
MAX_ORDERS_PER_DAY = 20    # hard daily order-count cap (BL-03)
MAX_PER_SECTOR = 2         # at most this many holdings from one sector
STOP_LOSS_PCT = 0.10       # sell a position that is down this much from cost
DAILY_LOSS_LIMIT = 0.03    # account down this much today -> no new buys


def dry_run_enabled() -> bool:
    """DRY_RUN is ON unless explicitly set to a falsey string. Safe by default (BL-05)."""
    return os.getenv("DRY_RUN", "true").strip().lower() not in {"0", "false", "no", "off"}


def kill_switch_active(path: Path = KILL_SWITCH) -> bool:
    """True if a KILL_SWITCH file exists at the repo root (BL-04)."""
    return path.exists()


def latest_signals(universe: list[str], start: str = "2015-01-01") -> dict[str, float]:
    """Train per ticker on its history and return each ticker's latest P(up)."""
    proba: dict[str, float] = {}
    for ticker in universe:
        try:
            df = add_features(fetch_price_history(ticker, start))
            model, _acc, _tr, _te = train_model(df)
            backend = RandomForestBackend.from_fitted(model)
            latest = df[FEATURE_COLUMNS].iloc[[-1]]
            proba[ticker] = float(backend.predict_proba_up(latest).iloc[0])
        except Exception:  # noqa: BLE001 — one bad ticker shouldn't sink the run
            continue
    return proba


def plan_orders(
    broker,
    universe: list[str] | None = None,
    top_n_count: int = 5,
    order_usd: float = MAX_ORDER_USD,
    trading_day: date | None = None,
    signals_out: dict | None = None,
    risk_out: list | None = None,
) -> list[Order]:
    """Compute today's intended orders (no submission). Used by the Preview step.

    If `signals_out` is a dict it is filled with each ticker's P(up) so the caller can log it. Risk rules
    (sector cap, stop-loss, daily-loss halt) are applied; if `risk_out` is a list it receives plain-English
    notes about any rule that changed the plan. Stop-loss and daily-loss need a broker that reports
    positions' P&L / account change (Alpaca); other brokers skip those two.
    """
    universe = universe or list(DEFAULT_UNIVERSE)
    day = trading_day or trading_day_today()
    proba = latest_signals(universe)
    if signals_out is not None:
        signals_out.update(proba)

    notes = risk_out if risk_out is not None else []
    managed = set(universe)  # the bot only touches its own universe; anything else (e.g. a manual SPY buy) is left alone
    details = [d for d in (broker.get_position_details() if hasattr(broker, "get_position_details") else [])
               if d["ticker"] in managed]
    stopped = stop_loss_tickers(details, STOP_LOSS_PCT)
    if stopped:
        notes.append(f"Stop-loss: {', '.join(stopped)} down {STOP_LOSS_PCT:.0%}+ from cost — sell, don't re-buy today.")
    ranked = [t for t in sorted(proba, key=proba.get, reverse=True) if t not in stopped]
    target = apply_sector_cap(ranked, top_n_count, MAX_PER_SECTOR, SECTORS)
    plain = apply_sector_cap(ranked, top_n_count, None, SECTORS)
    if target != plain:
        notes.append(f"Sector cap ({MAX_PER_SECTOR} per sector) swapped out: {', '.join(sorted(set(plain) - set(target)))}.")

    current = {t: q for t, q in broker.get_positions().items() if t in managed}
    orders = diff(current, target, day, max_positions=top_n_count)
    # Size buys in dollars; sells close the existing share quantity.
    sized = []
    for o in orders:
        if o.side == "buy":
            sized.append(Order(o.ticker, "buy", o.client_order_id, notional=order_usd))
        else:
            sized.append(Order(o.ticker, "sell", o.client_order_id, qty=current.get(o.ticker)))
    if hasattr(broker, "get_account_summary"):
        day = broker.get_account_summary().get("day_pl_pct")
        if daily_loss_halt(day, DAILY_LOSS_LIMIT):
            notes.append(f"Daily loss limit hit (account {day:+.1%} today, limit -{DAILY_LOSS_LIMIT:.0%}): new buys paused.")
            sized = [o for o in sized if o.side == "sell"]
    return sized


def enforce_caps(
    orders: list[Order],
    max_orders: int = MAX_ORDERS_PER_DAY,
    max_order_usd: float = MAX_ORDER_USD,
) -> None:
    """Raise if the order set breaches a hard cap. Never silently truncate (BL-02/03)."""
    if len(orders) > max_orders:
        raise ValueError(f"{len(orders)} orders exceeds MAX_ORDERS_PER_DAY={max_orders}")
    for o in orders:
        if o.notional is not None and o.notional > max_order_usd:
            raise ValueError(
                f"{o.ticker} order ${o.notional:.2f} exceeds MAX_ORDER_USD={max_order_usd}"
            )


def _log_orders(orders: list[Order], status: str, day: date, log_path: Path = ORDER_LOG) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not log_path.exists()
    with log_path.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["date", "ticker", "side", "notional", "qty", "client_order_id", "status"])
        for o in orders:
            w.writerow([day, o.ticker, o.side, o.notional, o.qty, o.client_order_id, status])


def submit_orders(
    broker,
    orders: list[Order],
    trading_day: date | None = None,
    dry_run: bool | None = None,
    kill_switch_path: Path = KILL_SWITCH,
    log_path: Path = ORDER_LOG,
) -> dict:
    """Submit (or log) the planned orders with every safety rail applied."""
    day = trading_day or trading_day_today()
    dry = dry_run_enabled() if dry_run is None else dry_run

    if kill_switch_active(kill_switch_path):
        _log_orders(orders, "halted_kill_switch", day, log_path)
        return {"submitted": 0, "status": "halted", "reason": "KILL_SWITCH present"}

    enforce_caps(orders)

    if dry:
        _log_orders(orders, "dry_run", day, log_path)
        return {"submitted": 0, "status": "dry_run", "planned": len(orders)}

    submitted = 0
    for o in orders:
        broker.submit_order(o)
        submitted += 1
    _log_orders(orders, "submitted", day, log_path)
    return {"submitted": submitted, "status": "submitted"}


def run_eod(
    broker,
    universe: list[str] | None = None,
    top_n_count: int = 5,
    order_usd: float = MAX_ORDER_USD,
    trading_day: date | None = None,
    dry_run: bool | None = None,
) -> dict:
    """Full loop: plan today's orders, enforce caps, then submit or log them."""
    day = trading_day or trading_day_today()
    orders = plan_orders(broker, universe, top_n_count, order_usd, day)
    return submit_orders(broker, orders, day, dry_run=dry_run)

"""End-of-day paper-trading bot loop.

This module is PURE: only definitions and constants at import time — importing
`bot` never touches the network or submits an order (Pitfall #20). Trading runs
only when a function here is called explicitly.

Safety rails: DRY_RUN defaults ON (orders are logged, never sent, unless DRY_RUN
is explicitly false), a KILL_SWITCH file at the repo root halts submission, and
hard caps bound per-order dollars and daily order count (Pitfall #8).
"""

import csv
import json
import os
from datetime import date, timedelta
from pathlib import Path

from stock_ai.config import DEFAULT_UNIVERSE, SECTORS
from stock_ai.execution.base import Order, make_client_order_id
from stock_ai.execution.clock import trading_day_today
from stock_ai.execution.diff import diff
from stock_ai.execution.risk import apply_sector_cap, daily_loss_halt, stop_loss_tickers
from stock_ai.models.live import evaluate_ticker

REPO_ROOT = Path(__file__).resolve().parent
KILL_SWITCH = REPO_ROOT / "KILL_SWITCH"
ORDER_LOG = REPO_ROOT / "logs" / "orders.csv"
SIGNAL_LOG = REPO_ROOT / "logs" / "signals.csv"
COOLDOWN_FILE = REPO_ROOT / "logs" / "stopped_out.json"

MAX_ORDER_USD = 500.0      # hard per-order dollar cap (BL-02)
MAX_ORDERS_PER_DAY = 20    # hard daily order-count cap (BL-03)
MAX_PER_SECTOR = 2         # at most this many holdings from one sector
STOP_LOSS_PCT = 0.10       # sell a position that is down this much from cost
DAILY_LOSS_LIMIT = 0.03    # account down this much today -> no new buys
COOLDOWN_DAYS = 7          # a stopped-out ticker is not re-bought for this many calendar days
MIN_SIGNAL_COVERAGE = 0.8  # refuse to trade if fewer than this share of the universe could be scored


def dry_run_enabled() -> bool:
    """DRY_RUN is ON unless explicitly set to a falsey string. Safe by default (BL-05)."""
    return os.getenv("DRY_RUN", "true").strip().lower() not in {"0", "false", "no", "off"}


def kill_switch_active(path: Path = KILL_SWITCH) -> bool:
    """True if a KILL_SWITCH file exists at the repo root (BL-04)."""
    return path.exists()


def evaluate_universe(universe: list[str]) -> tuple[dict[str, float], dict[str, bool]]:
    """Score every ticker the way the app does: ({ticker: P(up)}, {ticker: has a reliable edge}).

    A ticker whose data can't be loaded is simply absent from both dicts; the caller decides what that means.
    """
    proba: dict[str, float] = {}
    edge: dict[str, bool] = {}
    for ticker in universe:
        try:
            r = evaluate_ticker(ticker)
        except Exception:  # noqa: BLE001 — one bad ticker shouldn't sink the run
            continue
        proba[ticker], edge[ticker] = r["p_up"], r["has_edge"]
    return proba, edge


def load_cooldown(today: date, path: Path | None = None) -> set[str]:
    """Tickers stopped out within the last COOLDOWN_DAYS days (not to be re-bought yet)."""
    try:
        data = json.loads((path or COOLDOWN_FILE).read_text())
    except (OSError, ValueError):
        return set()
    cutoff = (today - timedelta(days=COOLDOWN_DAYS)).isoformat()
    return {t for t, d in data.items() if d >= cutoff}


def record_stops(tickers: list[str], today: date, path: Path | None = None) -> None:
    """Remember that these tickers were stopped out today."""
    if not tickers:
        return
    path = path or COOLDOWN_FILE
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    data.update({t: today.isoformat() for t in tickers})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def plan_orders(
    broker,
    universe: list[str] | None = None,
    top_n_count: int = 5,
    order_usd: float = MAX_ORDER_USD,
    trading_day: date | None = None,
    signals_out: dict | None = None,
    risk_out: list | None = None,
    stopped_out: list | None = None,
    require_edge: bool = True,
) -> list[Order]:
    """Compute today's intended orders (no submission). Used by the Preview step.

    If `signals_out` is a dict it is filled with each ticker's P(up) so the caller can log it. Risk rules
    (sector cap, stop-loss, daily-loss halt) are applied; if `risk_out` is a list it receives plain-English
    notes about any rule that changed the plan. Stop-loss and daily-loss need a broker that reports
    positions' P&L / account change (Alpaca); other brokers skip those two.
    """
    universe = universe or list(DEFAULT_UNIVERSE)
    day = trading_day or trading_day_today()
    proba, edge = evaluate_universe(universe)
    if signals_out is not None:
        signals_out.update(proba)
    if len(proba) < MIN_SIGNAL_COVERAGE * len(universe):
        raise RuntimeError(f"Only {len(proba)} of {len(universe)} tickers could be scored (data problem?); "
                           "refusing to plan orders from a partial picture.")

    notes = risk_out if risk_out is not None else []
    managed = set(universe)  # the bot only touches its own universe; anything else (e.g. a manual SPY buy) is left alone
    details = [d for d in (broker.get_position_details() if hasattr(broker, "get_position_details") else [])
               if d["ticker"] in managed]
    stopped = stop_loss_tickers(details, STOP_LOSS_PCT)
    if stopped:
        notes.append(f"Stop-loss: {', '.join(stopped)} down {STOP_LOSS_PCT:.0%}+ from cost — sell, and no re-buy for {COOLDOWN_DAYS} days.")
        if stopped_out is not None:
            stopped_out.extend(stopped)
    cooling = load_cooldown(day)
    ranked = [t for t in sorted(proba, key=proba.get, reverse=True) if t not in stopped and t not in cooling]
    if require_edge:
        no_edge = [t for t in ranked if not edge.get(t)]
        ranked = [t for t in ranked if edge.get(t)]
        if no_edge:
            notes.append(f"No reliable edge on {len(no_edge)} of {len(proba)} tickers — the bot only buys names where "
                         "the model beats the base rate with statistical confidence.")
    target = apply_sector_cap(ranked, top_n_count, MAX_PER_SECTOR, SECTORS)
    plain = apply_sector_cap(ranked, top_n_count, None, SECTORS)
    if target != plain:
        notes.append(f"Sector cap ({MAX_PER_SECTOR} per sector) swapped out: {', '.join(sorted(set(plain) - set(target)))}.")

    current = {t: q for t, q in broker.get_positions().items() if t in managed}
    # A held ticker we couldn't score today is a data problem, not a sell signal: leave it alone.
    unscored = sorted(t for t in current if t not in proba and t not in stopped)
    if unscored:
        notes.append(f"No data today for {', '.join(unscored)} — holding them rather than selling blind.")
    orders = [o for o in diff(current, target, day, max_positions=top_n_count)
              if not (o.side == "sell" and o.ticker in unscored)]
    # Size buys in dollars; sells close the existing share quantity.
    sized = []
    for o in orders:
        if o.side == "buy":
            sized.append(Order(o.ticker, "buy", o.client_order_id, notional=order_usd))
        else:
            sized.append(Order(o.ticker, "sell", o.client_order_id, qty=current.get(o.ticker)))
    if hasattr(broker, "get_account_summary"):
        day_pl = broker.get_account_summary().get("day_pl_pct")
        if daily_loss_halt(day_pl, DAILY_LOSS_LIMIT):
            notes.append(f"Daily loss limit hit (account {day_pl:+.1%} today, limit -{DAILY_LOSS_LIMIT:.0%}): new buys paused.")
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


def _sent_today(day: date, log_path: Path) -> set[str]:
    """client_order_ids already submitted (not dry-run) on `day`, from the order log."""
    try:
        with log_path.open(newline="") as f:
            return {r["client_order_id"] for r in csv.DictReader(f)
                    if r["date"] == str(day) and r["status"] == "submitted"}
    except OSError:
        return set()


def submit_orders(
    broker,
    orders: list[Order],
    trading_day: date | None = None,
    dry_run: bool | None = None,
    kill_switch_path: Path = KILL_SWITCH,
    log_path: Path = ORDER_LOG,
) -> dict:
    """Submit (or log) the planned orders with every safety rail applied.

    Each order is sent and logged on its own, so one rejected order cannot hide the ones already sent.
    The orders-per-day cap counts what this day's log already holds, not just this batch.
    """
    day = trading_day or trading_day_today()
    dry = dry_run_enabled() if dry_run is None else dry_run

    if kill_switch_active(kill_switch_path):
        _log_orders(orders, "halted_kill_switch", day, log_path)
        return {"submitted": 0, "status": "halted", "reason": "KILL_SWITCH present"}

    enforce_caps(orders)

    if dry:
        _log_orders(orders, "dry_run", day, log_path)
        return {"submitted": 0, "status": "dry_run", "planned": len(orders)}

    already = _sent_today(day, log_path)
    fresh = [o for o in orders if o.client_order_id not in already]
    if len(already) + len(fresh) > MAX_ORDERS_PER_DAY:
        raise ValueError(f"{len(already)} orders already sent today + {len(fresh)} new exceeds "
                         f"MAX_ORDERS_PER_DAY={MAX_ORDERS_PER_DAY}")

    submitted, failed = 0, []
    for o in orders:
        try:
            broker.submit_order(o)
        except Exception as exc:  # noqa: BLE001 — keep going; report every failure
            _log_orders([o], f"failed: {type(exc).__name__}", day, log_path)
            failed.append((o.ticker, f"{type(exc).__name__}: {exc}"))
            continue
        _log_orders([o], "submitted", day, log_path)
        submitted += 1
    return {"submitted": submitted, "failed": failed, "status": "partial" if failed else "submitted"}


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

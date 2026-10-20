"""Daily after-close job: log signals, rebalance the Alpaca PAPER account, log news picks, grade old calls.

Run by launchd on weekdays (see scripts/install_daily_job.py). Safe to run repeatedly: it does the work once
per trading day, skips non-trading days, and order ids are idempotent. Paper account only.

  python scripts/daily_job.py            # log + grade only (no orders)
  python scripts/daily_job.py --trade    # also submit the top-N paper orders (caps and KILL_SWITCH apply)
  python scripts/daily_job.py --force    # ignore the time-of-day / already-done guards
"""

import argparse
import json
import sys
import traceback
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ET = ZoneInfo("America/New_York")
STATE = ROOT / "logs" / "daily_state.json"
RUN_AFTER, RUN_BEFORE = time(16, 15), time(20, 0)   # ET: after the close, with margin for late wake-ups
TOP_N = 10


def should_run(now: datetime, last_done: str | None, force: bool = False) -> tuple[bool, str]:
    """Weekday, after the close, and not already done today (ET)."""
    if force:
        return True, "forced"
    if now.weekday() >= 5:
        return False, "weekend"
    if not (RUN_AFTER <= now.time() <= RUN_BEFORE):
        return False, f"outside run window ({RUN_AFTER:%H:%M}-{RUN_BEFORE:%H:%M} ET)"
    if last_done == now.date().isoformat():
        return False, "already done today"
    return True, "ok"


def _closes(ticker: str, **kw):
    """Daily closes as a Series (yfinance may return a one-column frame)."""
    import time

    import yfinance as yf

    for attempt in range(4):  # Yahoo sometimes returns an empty frame; retry before giving up
        s = yf.download(ticker, progress=False, auto_adjust=True, **kw)["Close"]
        s = (s.iloc[:, 0] if s.ndim == 2 else s).dropna()
        if len(s):
            return s
        time.sleep(5 * (attempt + 1))
    return s


def _notify(title: str, msg: str) -> None:
    """Best-effort macOS notification (never raises)."""
    import subprocess

    try:
        safe = lambda t: t.replace("\\", " ").replace('"', "'")[:180]  # noqa: E731
        subprocess.run(["osascript", "-e", f'display notification "{safe(msg)}" with title "{safe(title)}"'],
                       check=False, timeout=10, capture_output=True)
    except Exception:  # noqa: BLE001
        pass


def _log(msg: str) -> None:
    line = f"{datetime.now(ET):%Y-%m-%d %H:%M:%S %Z}  {msg}"
    print(line, flush=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    with (ROOT / "logs" / "daily_job.log").open("a") as f:
        f.write(line + "\n")


def run(trade: bool, force: bool) -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    import pandas as pd
    import bot
    from stock_ai.config import DEFAULT_UNIVERSE
    from stock_ai.data.news import fetch_news, rank_tickers
    from stock_ai.execution.paper import AlpacaPaperBroker
    from stock_ai.execution.signal_log import log_signals, resolve_outcomes

    now = datetime.now(ET)
    last = json.loads(STATE.read_text()).get("last_done") if STATE.exists() else None
    ok, why = should_run(now, last, force)
    if not ok:
        _log(f"skip: {why}")
        return 0

    spy = _closes("SPY", period="5d")
    if not len(spy):
        _log("no SPY data from Yahoo; will retry on the next scheduled run")
        return 1
    if not force and spy.index[-1].date() != now.date():
        _log("skip: market did not trade today (holiday?)")
        return 0
    _log(f"start (trade={trade}, dry_run_env={bot.dry_run_enabled()})")

    broker = AlpacaPaperBroker()
    sigs: dict = {}
    notes: list = []
    stopped: list = []
    orders = bot.plan_orders(broker, universe=list(DEFAULT_UNIVERSE), top_n_count=TOP_N, signals_out=sigs,
                             risk_out=notes, stopped_out=stopped)
    for n in notes:
        _log(f"risk rule: {n}")
    if notes:
        _notify("Stock AI: risk rule applied", " ".join(notes))
    bot.enforce_caps(orders)
    px = {}
    for t in sigs:
        c = _closes(t, period="5d")
        if len(c):
            px[t] = float(c.iloc[-1])
        else:
            _log(f"no price for {t}; leaving it out of the signal log")
    sigs = {t: v for t, v in sigs.items() if t in px}
    added = log_signals(sigs, px, bot.trading_day_today(), bot.SIGNAL_LOG, overwrite=True)
    _log(f"signals logged: {added} new of {len(sigs)}")

    # --trade asks to send orders, but the DRY_RUN switch still wins: both must agree before anything is sent.
    dry = bot.dry_run_enabled() or not trade
    result = bot.submit_orders(broker, orders, dry_run=dry)
    _log(f"orders {[(o.ticker, o.side) for o in orders]} -> {result}")
    if result["status"] == "submitted" or result["status"] == "partial":
        bot.record_stops(stopped, bot.trading_day_today())
    if result.get("failed"):
        _notify("Stock AI: some orders FAILED", "; ".join(f"{t}: {m}" for t, m in result["failed"])[:200])

    try:
        ranked = rank_tickers(fetch_news(list(DEFAULT_UNIVERSE), days=3, use_llm=True), list(DEFAULT_UNIVERSE))
        picks = ranked[ranked["label"] == "Bullish"].head(5)
        n = log_signals({r.ticker: (r.sentiment + 1) / 2 for r in picks.itertuples() if r.ticker in px},
                        {t: px[t] for t in picks["ticker"] if t in px}, bot.trading_day_today(),
                        bot.REPO_ROOT / "logs" / "news_picks.csv")
        _log(f"news picks logged: {n} ({', '.join(picks['ticker'])})")
    except Exception as exc:  # noqa: BLE001 — news trouble must not block the trading part
        _log(f"news step failed: {type(exc).__name__}: {exc}")

    for path in (bot.SIGNAL_LOG, bot.REPO_ROOT / "logs" / "news_picks.csv"):
        if path.exists():
            raw = pd.read_csv(path)
            closes = {t: _closes(t, start=str(raw["date"].min())) for t in raw["ticker"].unique()}
            log = resolve_outcomes(closes, path)
            _log(f"graded {path.name}: {int(log['went_up'].notna().sum())}/{len(log)} resolved")

    try:   # proposals only: a review is written down for a human, never sent to the broker
        from stock_ai.execution.review import build_context, review_day, rule_based_review, save_review
        from stock_ai.execution.signal_log import live_accuracy

        acct, pos = broker.get_account_summary(), broker.get_position_details()
        live = live_accuracy(pd.read_csv(bot.SIGNAL_LOG)) if bot.SIGNAL_LOG.exists() else {"n": 0, "pending": 0}
        ctx = build_context(acct, pos, [{"side": o.side, "ticker": o.ticker} for o in orders], notes, sigs, live,
                            bot.trading_day_today())
        review = review_day(ctx, set(sigs), rule_based_review(acct, pos, notes, live, set(sigs)))
        save_review(review, bot.trading_day_today())
        _log(f"review ({review['source']}): {review['summary'][:160]} | {len(review['suggestions'])} suggestions")
    except Exception as exc:  # noqa: BLE001
        _log(f"review step failed: {type(exc).__name__}: {exc}")

    STATE.parent.mkdir(exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if dry:   # a dry run is logged but must not use up the day: the real run still has to happen
        state["last_dry"] = now.date().isoformat()
        _log(f"dry run only (DRY_RUN={'on' if bot.dry_run_enabled() else 'off'}, trade={trade}) — nothing sent")
    else:
        state["last_done"] = now.date().isoformat()
    STATE.write_text(json.dumps(state))
    _log("done")
    verb = "planned (dry run)" if dry else "placed"
    _notify("Stock AI: daily run done", (f"{len(orders)} orders {verb}: " + ", ".join(f"{o.side} {o.ticker}" for o in orders))
            if orders else "No order changes today.")
    return 1 if result.get("failed") else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trade", action="store_true", help="submit paper orders (otherwise dry run)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    try:
        sys.exit(run(args.trade, args.force))
    except Exception:  # noqa: BLE001
        _log("FAILED:\n" + traceback.format_exc())
        _notify("Stock AI: daily run FAILED", "Check logs/daily_job.log")
        sys.exit(1)

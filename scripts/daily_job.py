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
TOP_N = 5


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
    import yfinance as yf

    s = yf.download(ticker, progress=False, auto_adjust=True, **kw)["Close"]
    return (s.iloc[:, 0] if s.ndim == 2 else s).dropna()


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
    if not force and spy.index[-1].date() != now.date():
        _log("skip: market did not trade today (holiday?)")
        return 0
    _log(f"start (trade={trade}, dry_run_env={bot.dry_run_enabled()})")

    broker = AlpacaPaperBroker()
    sigs: dict = {}
    notes: list = []
    orders = bot.plan_orders(broker, universe=list(DEFAULT_UNIVERSE), top_n_count=TOP_N, signals_out=sigs, risk_out=notes)
    for n in notes:
        _log(f"risk rule: {n}")
    bot.enforce_caps(orders)
    px = {t: float(_closes(t, period="5d").iloc[-1]) for t in sigs}
    added = log_signals(sigs, px, bot.trading_day_today(), bot.SIGNAL_LOG)
    _log(f"signals logged: {added} new of {len(sigs)}")

    result = bot.submit_orders(broker, orders, dry_run=False if trade else True)
    _log(f"orders {[(o.ticker, o.side) for o in orders]} -> {result}")

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

    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({"last_done": now.date().isoformat()}))
    _log("done")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trade", action="store_true", help="submit paper orders (otherwise dry run)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    try:
        sys.exit(run(args.trade, args.force))
    except Exception:  # noqa: BLE001
        _log("FAILED:\n" + traceback.format_exc())
        sys.exit(1)

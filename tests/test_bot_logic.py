"""Tests for bot safety rails: caps, kill switch, DRY_RUN, idempotent planning."""

from datetime import date

import pytest

import bot
from stock_ai.execution import FakeBroker, Order, make_client_order_id

DAY = date(2026, 10, 13)


def _orders(n):
    return [Order(f"T{i}", "buy", make_client_order_id(DAY, f"T{i}", "buy"), notional=100.0) for i in range(n)]


def test_dry_run_default_is_on(monkeypatch):
    monkeypatch.delenv("DRY_RUN", raising=False)
    assert bot.dry_run_enabled() is True


def test_dry_run_can_be_disabled(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    assert bot.dry_run_enabled() is False


def test_enforce_caps_rejects_too_many_orders():
    with pytest.raises(ValueError, match="MAX_ORDERS_PER_DAY"):
        bot.enforce_caps(_orders(21), max_orders=20)


def test_enforce_caps_rejects_oversized_order():
    big = [Order("AAPL", "buy", "cid", notional=999.0)]
    with pytest.raises(ValueError, match="MAX_ORDER_USD"):
        bot.enforce_caps(big, max_order_usd=500.0)


def test_dry_run_logs_but_does_not_submit(tmp_path):
    broker = FakeBroker(dry_run=False)
    log = tmp_path / "orders.csv"
    result = bot.submit_orders(
        broker, _orders(2), DAY, dry_run=True, kill_switch_path=tmp_path / "NONE", log_path=log
    )
    assert result["status"] == "dry_run"
    assert broker.submissions == []       # nothing submitted
    assert log.exists() and "dry_run" in log.read_text()


def test_kill_switch_halts_submission(tmp_path):
    broker = FakeBroker(dry_run=False)
    ks = tmp_path / "KILL_SWITCH"
    ks.write_text("stop")
    result = bot.submit_orders(
        broker, _orders(2), DAY, dry_run=False, kill_switch_path=ks, log_path=tmp_path / "o.csv"
    )
    assert result["status"] == "halted"
    assert broker.submissions == []


def test_live_path_submits_and_is_idempotent(tmp_path):
    broker = FakeBroker(dry_run=False)
    orders = _orders(2)
    kw = dict(trading_day=DAY, dry_run=False, kill_switch_path=tmp_path / "NONE", log_path=tmp_path / "o.csv")
    bot.submit_orders(broker, orders, **kw)
    bot.submit_orders(broker, orders, **kw)  # resubmit same day → no duplicates
    assert len(broker.submissions) == 2


def test_daily_job_runs_once_per_trading_day_after_the_close():
    import importlib.util
    from datetime import datetime
    from pathlib import Path
    from zoneinfo import ZoneInfo

    spec = importlib.util.spec_from_file_location("daily_job", Path(__file__).resolve().parent.parent / "scripts" / "daily_job.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    et = ZoneInfo("America/New_York")
    fri_eve, fri_noon, sat = (datetime(2026, 10, 16, 16, 40, tzinfo=et), datetime(2026, 10, 16, 12, 0, tzinfo=et),
                              datetime(2026, 10, 17, 16, 40, tzinfo=et))
    assert mod.should_run(fri_eve, None)[0]
    assert not mod.should_run(fri_eve, "2026-10-16")[0]      # already done today
    assert not mod.should_run(fri_noon, None)[0]             # market still open
    assert not mod.should_run(sat, None)[0]                  # weekend
    assert mod.should_run(fri_noon, None, force=True)[0]


class _Flaky:
    """Broker whose second order is rejected."""

    def __init__(self):
        self.sent = []

    def submit_order(self, order):
        if order.ticker == "BAD":
            raise ValueError("BAD is not tradable")
        self.sent.append(order.ticker)


def test_one_rejected_order_does_not_hide_the_others(tmp_path):
    import csv

    orders = [bot.Order("AAA", "buy", "d_AAA_buy", notional=100), bot.Order("BAD", "buy", "d_BAD_buy", notional=100),
              bot.Order("CCC", "buy", "d_CCC_buy", notional=100)]
    broker = _Flaky()
    log = tmp_path / "orders.csv"
    res = bot.submit_orders(broker, orders, dry_run=False, kill_switch_path=tmp_path / "KS", log_path=log)
    assert res["status"] == "partial" and res["submitted"] == 2 and res["failed"][0][0] == "BAD"
    assert broker.sent == ["AAA", "CCC"]
    statuses = {r["ticker"]: r["status"] for r in csv.DictReader(log.open())}
    assert statuses["AAA"] == "submitted" and statuses["BAD"].startswith("failed")


def test_orders_per_day_cap_counts_the_whole_day_not_one_batch(tmp_path):
    import pytest

    log = tmp_path / "orders.csv"
    kw = dict(dry_run=False, kill_switch_path=tmp_path / "KS", log_path=log, trading_day=__import__("datetime").date(2026, 1, 2))
    first = [bot.Order(f"T{i}", "buy", f"d_T{i}_buy", notional=10) for i in range(bot.MAX_ORDERS_PER_DAY - 5)]
    second = [bot.Order(f"U{i}", "buy", f"d_U{i}_buy", notional=10) for i in range(10)]
    bot.submit_orders(_Flaky(), first, **kw)
    with pytest.raises(ValueError, match="MAX_ORDERS_PER_DAY"):
        bot.submit_orders(_Flaky(), second, **kw)                       # (cap-5) + 10 > cap
    bot.submit_orders(_Flaky(), first, **kw)                           # same ids again: not new orders, fine

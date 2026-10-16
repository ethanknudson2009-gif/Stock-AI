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

"""Tests for the Broker Protocol, pure order-diff, and FakeBroker."""

from datetime import date

from stock_ai.execution import Broker, FakeBroker, Order, diff, make_client_order_id

DAY = date(2026, 10, 13)


def test_fake_broker_conforms_to_protocol():
    assert isinstance(FakeBroker(), Broker)


def test_client_order_id_is_deterministic():
    a = make_client_order_id(DAY, "AAPL", "buy")
    b = make_client_order_id(DAY, "AAPL", "buy")
    assert a == b == "2026-10-13_AAPL_buy"


def test_diff_empty_to_full_is_all_buys():
    orders = diff({}, ["AAPL", "MSFT"], DAY)
    assert {o.ticker for o in orders} == {"AAPL", "MSFT"}
    assert all(o.side == "buy" for o in orders)


def test_diff_full_to_empty_is_all_sells():
    orders = diff({"AAPL": 1.0, "MSFT": 1.0}, [], DAY)
    assert {o.ticker for o in orders} == {"AAPL", "MSFT"}
    assert all(o.side == "sell" for o in orders)


def test_diff_partial_rotation():
    orders = diff({"AAPL": 1.0, "MSFT": 1.0}, ["MSFT", "NVDA"], DAY)
    by_ticker = {o.ticker: o.side for o in orders}
    assert by_ticker == {"AAPL": "sell", "NVDA": "buy"}  # MSFT held → no order


def test_order_cap_enforced():
    # Target of 5 but cap 2 → only the first 2 priority tickers are bought.
    orders = diff({}, ["NVDA", "AAPL", "MSFT", "JPM", "KO"], DAY, max_positions=2)
    bought = {o.ticker for o in orders if o.side == "buy"}
    assert bought == {"NVDA", "AAPL"}


def test_diff_is_deterministic_sorted():
    o1 = diff({}, ["MSFT", "AAPL"], DAY)
    o2 = diff({}, ["AAPL", "MSFT"], DAY)
    assert [o.ticker for o in o1] == [o.ticker for o in o2]  # sorted, order-independent


def test_submit_order_records_and_updates_positions():
    b = FakeBroker(dry_run=False)
    b.submit_order(Order("AAPL", "buy", make_client_order_id(DAY, "AAPL", "buy")))
    assert b.get_positions() == {"AAPL": 1.0}
    assert len(b.submissions) == 1


def test_submit_order_idempotent_on_duplicate_client_order_id():
    b = FakeBroker(dry_run=False)
    order = Order("AAPL", "buy", make_client_order_id(DAY, "AAPL", "buy"))
    b.submit_order(order)
    b.submit_order(order)  # resubmit (e.g. Streamlit rerun / cron retry)
    assert len(b.submissions) == 1  # single submission only


def test_dry_run_short_circuit():
    b = FakeBroker(dry_run=True)
    b.submit_order(Order("AAPL", "buy", make_client_order_id(DAY, "AAPL", "buy")))
    assert b.submissions == []        # nothing submitted
    assert b.get_positions() == {}    # no position change
    assert len(b.dry_run_log) == 1    # but logged


def test_dry_run_reads_env(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    assert FakeBroker().dry_run is True
    monkeypatch.setenv("DRY_RUN", "false")
    assert FakeBroker().dry_run is False


def test_signal_log_records_once_and_resolves_outcomes(tmp_path):
    import pandas as pd

    from stock_ai.execution.signal_log import live_accuracy, log_signals, resolve_outcomes

    path = tmp_path / "signals.csv"
    assert log_signals({"AAA": 0.7, "BBB": 0.3}, {"AAA": 100.0, "BBB": 50.0}, "2024-01-02", path) == 2
    assert log_signals({"AAA": 0.7}, {"AAA": 100.0}, "2024-01-02", path) == 0   # same day, no duplicates
    idx = pd.bdate_range("2024-01-02", periods=8)
    closes = {"AAA": pd.Series(range(100, 108), index=idx, dtype=float),          # rises -> went_up
              "BBB": pd.Series([50.0] + [49.0] * 7, index=idx)}                   # falls  -> went down
    log = resolve_outcomes(closes, path)
    assert list(log["went_up"]) == [1.0, 0.0]
    acc = live_accuracy(log)
    assert acc["n"] == 2 and acc["accuracy"] == 1.0   # both calls (0.7 up, 0.3 down) were right

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


def test_sector_cap_skips_overweight_sector_and_goes_deeper():
    from stock_ai.execution.risk import apply_sector_cap

    sectors = {"A1": "Tech", "A2": "Tech", "A3": "Tech", "B1": "Fin", "C1": "Energy"}
    ranked = ["A1", "A2", "A3", "B1", "C1"]
    assert apply_sector_cap(ranked, 3, 2, sectors) == ["A1", "A2", "B1"]          # A3 skipped, next sector used
    assert apply_sector_cap(ranked, 3, None, sectors) == ["A1", "A2", "A3"]       # no cap
    assert apply_sector_cap(["X", "Y", "Z"], 2, 1, {}) == ["X", "Y"]               # unknown sectors never capped


def test_stop_loss_and_daily_loss_halt_thresholds():
    from stock_ai.execution.risk import daily_loss_halt, stop_loss_tickers

    pos = [{"ticker": "A", "pl_pct": -0.12}, {"ticker": "B", "pl_pct": -0.05}, {"ticker": "C", "pl_pct": 0.2}]
    assert stop_loss_tickers(pos, 0.10) == ["A"]
    assert daily_loss_halt(-0.031, 0.03) and not daily_loss_halt(-0.01, 0.03) and not daily_loss_halt(None, 0.03)


def test_plan_orders_applies_risk_rules_for_alpaca_like_broker(monkeypatch):
    import bot
    from stock_ai.execution import FakeBroker

    class RiskyBroker(FakeBroker):
        def get_position_details(self):
            return [{"ticker": "AAA", "pl_pct": -0.15}]

        def get_account_summary(self):
            return {"day_pl_pct": -0.05}

    monkeypatch.setattr(bot, "latest_signals", lambda universe: {"AAA": 0.9, "BBB": 0.8, "CCC": 0.7})
    broker = RiskyBroker(dry_run=False)
    broker.submit_order(bot.Order("AAA", "buy", "x1"))                  # we already hold AAA
    notes: list = []
    orders = bot.plan_orders(broker, universe=["AAA", "BBB", "CCC"], top_n_count=2, risk_out=notes)
    assert [(o.ticker, o.side) for o in orders] == [("AAA", "sell")]    # stopped out; buys paused by daily loss
    assert any("Stop-loss" in n for n in notes) and any("Daily loss" in n for n in notes)

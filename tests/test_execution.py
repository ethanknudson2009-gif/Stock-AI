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

    monkeypatch.setattr(bot, "evaluate_universe", lambda u: ({"AAA": 0.9, "BBB": 0.8, "CCC": 0.7}, dict.fromkeys("ABC", False) | {"AAA": True, "BBB": True, "CCC": True}))
    broker = RiskyBroker(dry_run=False)
    broker.submit_order(bot.Order("AAA", "buy", "x1"))                  # we already hold AAA
    notes: list = []
    orders = bot.plan_orders(broker, universe=["AAA", "BBB", "CCC"], top_n_count=2, risk_out=notes)
    assert [(o.ticker, o.side) for o in orders] == [("AAA", "sell")]    # stopped out; buys paused by daily loss
    assert any("Stop-loss" in n for n in notes) and any("Daily loss" in n for n in notes)


def test_bot_leaves_positions_outside_its_universe_alone(monkeypatch):
    import bot
    from stock_ai.execution import FakeBroker

    monkeypatch.setattr(bot, "evaluate_universe", lambda u: ({"AAA": 0.9, "BBB": 0.8}, {"AAA": True, "BBB": True}))
    broker = FakeBroker(dry_run=False)
    broker.submit_order(bot.Order("SPY", "buy", "manual-spy"))          # held, but not in the bot's universe
    orders = bot.plan_orders(broker, universe=["AAA", "BBB"], top_n_count=2)
    assert all(o.ticker != "SPY" for o in orders)                      # never sold
    assert {o.ticker for o in orders} == {"AAA", "BBB"}                # and it doesn't eat a top-N slot


def _plan(monkeypatch, broker, proba, edge, universe, top_n=2, **kw):
    import bot

    monkeypatch.setattr(bot, "evaluate_universe", lambda u: (proba, edge))
    monkeypatch.setattr(bot, "COOLDOWN_FILE", kw.pop("cooldown_file"))
    return bot.plan_orders(broker, universe=universe, top_n_count=top_n, **kw)


def test_data_outage_never_liquidates_positions(monkeypatch, tmp_path):
    import bot
    from stock_ai.execution import FakeBroker

    broker = FakeBroker(dry_run=False)
    for t in ("AAA", "BBB"):
        broker.submit_order(bot.Order(t, "buy", f"x_{t}"))
    cd = tmp_path / "cd.json"
    # total outage: nothing could be scored -> refuse, don't sell
    import pytest
    with pytest.raises(RuntimeError, match="refusing"):
        _plan(monkeypatch, broker, {}, {}, ["AAA", "BBB", "CCC", "DDD", "EEE"], cooldown_file=cd)
    # partial: AAA unscored but 4 of 5 others fine -> AAA is held, not sold
    proba = {"BBB": 0.9, "CCC": 0.8, "DDD": 0.7, "EEE": 0.6}
    orders = _plan(monkeypatch, broker, proba, dict.fromkeys(proba, True), ["AAA", "BBB", "CCC", "DDD", "EEE"],
                   cooldown_file=cd, risk_out=(notes := []))
    assert not any(o.ticker == "AAA" and o.side == "sell" for o in orders)
    assert any("holding them" in n for n in notes)


def test_bot_only_buys_names_with_a_reliable_edge(monkeypatch, tmp_path):
    from stock_ai.execution import FakeBroker

    monkeypatch.setenv("BOT_REQUIRE_EDGE", "true")                     # the real .env may say false
    proba = {"AAA": 0.9, "BBB": 0.8, "CCC": 0.7}
    orders = _plan(monkeypatch, FakeBroker(dry_run=False), proba, {"AAA": False, "BBB": True, "CCC": True},
                   list(proba), cooldown_file=tmp_path / "cd.json")
    assert {o.ticker for o in orders} == {"BBB", "CCC"}               # AAA ranks first but has no edge


def test_stopped_out_ticker_is_not_rebought_during_cooldown(monkeypatch, tmp_path):
    import bot
    from datetime import date
    from stock_ai.execution import FakeBroker

    cd = tmp_path / "cd.json"
    bot.record_stops(["AAA"], date(2026, 10, 20), cd)
    proba = {"AAA": 0.9, "BBB": 0.8, "CCC": 0.7}
    edge = dict.fromkeys(proba, True)
    orders = _plan(monkeypatch, FakeBroker(dry_run=False), proba, edge, list(proba), cooldown_file=cd,
                   trading_day=date(2026, 10, 22))
    assert "AAA" not in {o.ticker for o in orders}
    later = _plan(monkeypatch, FakeBroker(dry_run=False), proba, edge, list(proba), cooldown_file=cd,
                  trading_day=date(2026, 11, 5))
    assert "AAA" in {o.ticker for o in later}


def test_positions_are_sized_from_equity_without_margin_and_stay_near_target(monkeypatch, tmp_path):
    import bot
    from stock_ai.execution import FakeBroker

    class Acct(FakeBroker):
        def get_account(self):
            return {"cash": 60_000.0, "equity": 100_000.0}

        def get_position_details(self):
            return [{"ticker": "AAA", "qty": 1, "avg_entry": 500, "price": 500.0, "value": 500.0, "pl": 0, "pl_pct": 0.0}]

    proba = {"AAA": 0.9, "BBB": 0.8, "CCC": 0.7}
    broker = Acct(dry_run=False)
    broker.submit_order(bot.Order("AAA", "buy", "x"))                  # a tiny leftover $500 position
    orders = _plan(monkeypatch, broker, proba, dict.fromkeys(proba, True), list(proba), top_n=3, cooldown_file=tmp_path / "c.json")
    buys = {o.ticker: o.notional for o in orders if o.side == "buy"}
    assert set(buys) == {"AAA", "BBB", "CCC"}                          # AAA is topped up, BBB/CCC are new
    assert all(v <= 20_000.0 + 0.01 for v in buys.values())            # <= 20% of equity each
    assert sum(buys.values()) <= 60_000.0 * bot.CASH_BUFFER + 0.01     # never more than real cash
    assert buys["BBB"] == buys["CCC"]

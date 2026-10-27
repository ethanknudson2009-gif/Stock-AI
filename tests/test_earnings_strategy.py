from datetime import date, datetime
from zoneinfo import ZoneInfo

from stock_ai.earnings import strategy as st

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 27, 16, 20, tzinfo=ET)          # Tuesday evening; next open = Wed 9:30
DAY = date(2026, 10, 27)


def row(t, score, ts):
    return {"ticker": t, "score": score, "report_ts": ts.isoformat()}


WED_AMC = datetime(2026, 10, 28, 16, 0, tzinfo=ET)       # after tomorrow's open -> buyable
WED_BMO = datetime(2026, 10, 28, 8, 0, tzinfo=ET)        # before tomorrow's open -> too late to buy
THU = datetime(2026, 10, 29, 8, 0, tzinfo=ET)


def pos(t, value=3700.0, pl=0.0):
    return {"ticker": t, "qty": 10.0, "price": value / 10, "value": value, "pl_pct": pl}


def test_new_buys_need_a_report_after_tomorrows_open():
    rows = [row("AMC", 0.5, WED_AMC), row("BMO", 0.9, WED_BMO), row("THU", 0.4, THU)]
    assert st.choose_targets(rows, set(), NOW) == ["AMC", "THU"]    # BMO would already have moved at our fill


def test_held_names_stay_until_they_have_reported():
    rows = [row("HELD", 0.3, WED_BMO)]                            # reports tomorrow morning; we already own it
    assert st.choose_targets(rows, {"HELD"}, NOW) == ["HELD"]
    done = [row("HELD", 0.3, datetime(2026, 10, 27, 8, 0, tzinfo=ET))]
    assert st.choose_targets(done, {"HELD"}, NOW) == []             # reported -> not a target -> sold


def test_only_names_jev_leans_up_on_and_top_n_only():
    rows = [row(f"T{i}", 0.5 - i * 0.01, THU) for i in range(30)] + [row("NEG", -0.2, THU)]
    got = st.choose_targets(rows, set(), NOW)
    assert len(got) == 20 and "NEG" not in got and got[0] == "T0"


def test_plan_sells_reported_names_and_sizes_buys_from_equity_without_margin():
    rows = [row("NEW1", 0.5, THU), row("NEW2", 0.4, THU)]
    orders = st.plan(rows, [pos("OLD")], equity=100_000, cash=30_000, day=DAY, now=NOW)
    sells = {o.ticker for o in orders if o.side == "sell"}
    buys = {o.ticker: o.notional for o in orders if o.side == "buy"}
    assert sells == {"OLD"} and set(buys) == {"NEW1", "NEW2"}
    assert all(v <= 10_000 + 0.01 for v in buys.values())           # per-name cap = 10% of equity


def test_no_buys_when_cash_is_negative_and_nothing_is_sold():
    rows = [row("NEW1", 0.5, THU)]
    orders = st.plan(rows, [], equity=100_000, cash=-10_000, day=DAY, now=NOW)
    assert not orders                                               # never borrow


def test_stop_loss_and_cooldown_block_a_name():
    rows = [row("BAD", 0.9, THU), row("OK", 0.5, THU)]
    orders = st.plan(rows, [pos("BAD", pl=-0.12)], equity=100_000, cash=50_000, day=DAY, now=NOW, cooling={"BAD"})
    assert ("BAD", "sell") in {(o.ticker, o.side) for o in orders}
    assert "BAD" not in {o.ticker for o in orders if o.side == "buy"}


def test_daily_loss_halt_pauses_buys_but_not_sells():
    rows = [row("NEW", 0.5, THU)]
    orders = st.plan(rows, [pos("OLD")], equity=100_000, cash=50_000, day=DAY, now=NOW, day_pl_pct=-0.05)
    assert {(o.ticker, o.side) for o in orders} == {("OLD", "sell")}


def test_one_off_sell_proceeds_count_as_cash_so_buys_are_not_scaled_down():
    rows = [row("NEW1", 0.5, THU), row("NEW2", 0.4, THU)]
    spy = {"ticker": "SPY", "qty": 90.0, "price": 770.0, "value": 69_300.0, "pl_pct": 0.0}
    orders = st.plan(rows, [spy], equity=100_000, cash=-30_000, day=DAY, now=NOW, extra_sells=("SPY",))
    assert ("SPY", "sell") in {(o.ticker, o.side) for o in orders}      # sold only because it was named explicitly
    assert sum(o.notional for o in orders if o.side == "buy") == 2 * 10_000.0 * 1.0   # full-size buys (10% each)
    plain = st.plan(rows, [spy], equity=100_000, cash=-30_000, day=DAY, now=NOW, universe={"NEW1", "NEW2"})
    assert ("SPY", "sell") not in {(o.ticker, o.side) for o in plain}   # never touched unless asked

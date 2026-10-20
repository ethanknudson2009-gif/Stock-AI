"""Regression tests for the problems found in the full audit (2026-10-20)."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")


def test_order_signal_day_comes_from_the_order_id_not_the_acceptance_time():
    import ui_common as u

    accepted = datetime(2026, 10, 19, 4, 0, tzinfo=ET)                 # Alpaca stamps a Friday-evening order Monday 4 AM
    assert u.order_signal_day("2026-10-16_AVGO_buy", accepted, True) == "2026-10-16"
    assert u.order_signal_day("9d6e9e69-2493", accepted, False) == "2026-10-19"   # manual order: no signal date


def test_equity_chart_reads_dates_in_utc_skips_weekends_and_adds_live_equity():
    import ui_common as u

    def ts(y, m, d):
        return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())

    pts = [(ts(2026, 10, 16), 100000.0), (ts(2026, 10, 17), 100000.0), (ts(2026, 10, 20), 99942.7)]  # Fri, Sat, Tue
    fig = u.equity_history_chart(pts, live_equity=100014.61)
    xs = list(fig.data[0].x)
    assert xs[0] == date(2026, 10, 16)                                  # not shifted back to the 15th
    assert date(2026, 10, 17) not in xs                                 # Saturday dropped
    assert fig.data[0].y[-1] == 100014.61                               # today's live value is the last point


def test_latest_trading_day_waits_for_the_close():
    import ui_common as u

    tue_midday = datetime(2026, 10, 20, 12, 0, tzinfo=ET)
    tue_evening = datetime(2026, 10, 20, 16, 30, tzinfo=ET)
    sat = datetime(2026, 10, 24, 11, 0, tzinfo=ET)
    assert u.latest_trading_day(tue_midday) == date(2026, 10, 19)       # today's bar isn't final yet
    assert u.latest_trading_day(tue_evening) == date(2026, 10, 20)
    assert u.latest_trading_day(sat) == date(2026, 10, 23)


def test_unfinished_bar_is_dropped_while_the_market_is_open():
    from stock_ai.models.live import drop_unfinished_bar

    df = pd.DataFrame({"Close": [1.0, 2.0]}, index=pd.to_datetime(["2026-10-19", "2026-10-20"]))
    assert len(drop_unfinished_bar(df, datetime(2026, 10, 20, 11, 0, tzinfo=ET))) == 1
    assert len(drop_unfinished_bar(df, datetime(2026, 10, 20, 16, 30, tzinfo=ET))) == 2


def test_sma_crossover_needs_history_before_the_window():
    from stock_ai.strategy.baselines import sma_crossover_positions

    vals = np.r_[np.full(300, 200.0), np.full(100, 100.0), np.linspace(100, 110, 50)]   # crash, then a small bounce
    idx = pd.date_range("2024-01-01", periods=len(vals), freq="B")
    full = sma_crossover_positions(pd.DataFrame({"Close": pd.Series(vals, index=idx)}))
    cut = sma_crossover_positions(pd.DataFrame({"Close": pd.Series(vals, index=idx).iloc[-150:]}))
    assert full.iloc[-1] == 0          # the true 200-day average still remembers the high prices
    assert cut.iloc[-1] == 1           # a window-trimmed series forgets them and wrongly says "long"


def test_signal_log_overwrite_replaces_ungraded_rows_and_reading_does_not_rewrite(tmp_path):
    from stock_ai.execution.signal_log import log_signals, resolve_outcomes

    path = tmp_path / "s.csv"
    log_signals({"AAA": 0.6}, {"AAA": 100.0}, "2026-10-20", path)                    # mid-day preview
    assert log_signals({"AAA": 0.7}, {"AAA": 101.0}, "2026-10-20", path) == 0        # normal: first writer wins
    assert log_signals({"AAA": 0.7}, {"AAA": 101.0}, "2026-10-20", path, overwrite=True) == 1   # scheduled job wins
    row = pd.read_csv(path).iloc[0]
    assert row["p_up"] == 0.7 and row["price"] == 101.0
    before = path.stat().st_mtime_ns
    resolve_outcomes({"AAA": pd.Series([1.0], index=pd.to_datetime(["2026-10-21"]))}, path)   # nothing to grade yet
    assert path.stat().st_mtime_ns == before


def test_claude_reply_with_nan_is_ignored_not_turned_into_a_buy_score():
    from stock_ai.data.sentiment import _parse

    assert _parse('{"1": NaN, "2": 0.4, "3": 9}') == {"2": 0.4, "3": 1.0}


def test_news_dedupes_reposted_headlines(monkeypatch):
    from types import SimpleNamespace

    from stock_ai.data import news

    class Client:
        def __init__(self, *a): pass

        def get_news(self, req):
            mk = lambda i, h: SimpleNamespace(id=i, created_at=datetime(2026, 10, 20, tzinfo=timezone.utc), headline=h,
                                              summary="", source="Benzinga", url="u", symbols=["AAPL"])
            return SimpleNamespace(data={"news": [mk(1, "Apple beats"), mk(2, "Apple beats"), mk(3, "Other")]})

    monkeypatch.setattr("alpaca.data.historical.news.NewsClient", Client)
    monkeypatch.setattr(news, "load_settings", lambda: SimpleNamespace(alpaca_api_key="k", alpaca_secret_key="s"))
    assert len(news.fetch_news(["AAPL"], days=1)) == 2


def test_account_snapshot_turns_network_errors_into_a_message(monkeypatch):
    import ui_common as u

    class Boom:
        def __init__(self): raise ConnectionError("SSL: CERTIFICATE_VERIFY_FAILED")

    monkeypatch.setattr("stock_ai.execution.paper.AlpacaPaperBroker", Boom)
    u.account_snapshot.clear()
    snap = u.account_snapshot()
    assert snap and "CERTIFICATE_VERIFY_FAILED" in snap["error"]
    u.account_snapshot.clear()


def test_daily_job_respects_dry_run_and_dry_runs_do_not_use_up_the_day():
    import importlib.util
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "scripts" / "daily_job.py").read_text()
    assert "dry = bot.dry_run_enabled() or not trade" in src             # --trade can't override DRY_RUN
    assert 'state["last_dry"]' in src and 'state["last_done"]' in src

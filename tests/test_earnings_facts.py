from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from stock_ai.earnings import facts

ET = ZoneInfo("America/New_York")


def test_beat_stats_counts_beats_and_average_surprise():
    past = pd.DataFrame({"EPS Estimate": [1.0, 2.0, 1.0, None], "Reported EPS": [1.1, 1.8, 1.0, None]})
    b = facts.beat_stats(past)
    assert b["n"] == 3 and b["beats"] == 1                           # 1.0 vs 1.0 is a meet, not a beat
    assert abs(b["avg_surprise_pct"] - 0.0) < 1e-9                   # +10%, -10%, 0%
    assert facts.beat_stats(pd.DataFrame({"EPS Estimate": [None], "Reported EPS": [None]})) is None


def _closes():
    idx = pd.bdate_range("2026-01-05", periods=10, tz=ET)             # Mon Jan 5 .. Fri Jan 16
    return pd.Series([100, 100, 110, 110, 110, 110, 110, 99, 99, 99], index=idx)


def test_before_open_report_uses_previous_close_to_that_close():
    ts = datetime(2026, 1, 7, 8, 0, tzinfo=ET)                        # Wed 8 AM: Tue 100 -> Wed 110
    assert abs(facts.reaction_moves(_closes(), [ts])[0] - 0.10) < 1e-9


def test_after_close_report_uses_that_close_to_next_close():
    ts = datetime(2026, 1, 13, 16, 0, tzinfo=ET)                      # Tue 4 PM: Tue close 110 -> Wed close 99
    assert abs(facts.reaction_moves(_closes(), [ts])[0] - (-0.10)) < 1e-9


def test_reaction_for_a_report_without_enough_prices_is_skipped():
    assert facts.reaction_moves(_closes(), [datetime(2026, 1, 16, 16, 0, tzinfo=ET)]) == []   # no next-day close yet


def test_implied_move_is_straddle_over_price():
    calls = pd.DataFrame({"strike": [95.0, 100.0, 105.0], "bid": [7, 4, 2], "ask": [8, 5, 3], "lastPrice": [7, 4, 2]})
    puts = pd.DataFrame({"strike": [95.0, 100.0, 105.0], "bid": [2, 3.5, 6], "ask": [3, 4.5, 7], "lastPrice": [2, 4, 6]})
    assert abs(facts.implied_move(calls, puts, 100.0) - 0.085) < 1e-9   # (4.5 + 4.0) / 100
    assert facts.implied_move(calls.iloc[0:0], puts, 100.0) is None


def test_describe_says_when_a_fact_is_missing():
    text = facts.describe({"beats": None, "moves": None, "implied": None})
    assert text.count("not available") == 3
    full = facts.describe({"beats": {"n": 8, "beats": 7, "avg_surprise_pct": 4.2}, "moves": [0.03, -0.02], "implied": 0.058})
    assert "7 of its last 8" in full and "+3.0%, -2.0%" in full and "5.8%" in full

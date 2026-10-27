from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from stock_ai.earnings import jev, scan as sc

ET = ZoneInfo("America/New_York")


@pytest.fixture(autouse=True)
def no_network_facts(monkeypatch):
    from stock_ai.earnings import facts
    monkeypatch.setattr(facts, "company_facts", lambda *a, **k: {"beats": None, "moves": None, "implied": None})


def _ans(up, down, beat, conf=0.8):
    return {"beat": {"noul": beat}, "reaction": {"probabilities": {"up": up, "flat": 1 - up - down, "down": down},
                                                "confidence": conf}}


def test_score_prefers_likely_up_and_likely_beat():
    good = sc.score_answer(_ans(0.7, 0.1, 0.9))[-1]
    meh = sc.score_answer(_ans(0.7, 0.1, 0.1))[-1]
    bad = sc.score_answer(_ans(0.1, 0.7, 0.5))[-1]
    assert good > meh > 0 > bad


NOW = datetime(2026, 10, 27, 16, 20, tzinfo=ET)
INFO = (datetime(2026, 10, 29, 8, 0, tzinfo=ET), 1.0, 1.2, 1.1, 100.0)


def test_scan_ranks_and_logs_once_per_day(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "LOG", tmp_path / "picks.csv")
    monkeypatch.setattr(sc, "next_report", lambda t, now, days: INFO if t != "CCC" else None)
    answers = {"AAA": _ans(0.8, 0.05, 0.9), "BBB": _ans(0.3, 0.4, 0.4)}
    monkeypatch.setattr(jev, "ask", lambda state, **kw: answers["AAA" if "AAA" in state else "BBB"])
    rows = sc.scan(["AAA", "BBB", "CCC"], now=NOW)
    assert [r["ticker"] for r in rows] == ["AAA", "BBB"]               # CCC isn't reporting -> skipped
    sc.scan(["AAA", "BBB", "CCC"], now=NOW)
    assert len((tmp_path / "picks.csv").read_text().splitlines()) == 3  # header + 2 rows, not duplicated


def test_scan_raises_if_jev_returns_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "LOG", tmp_path / "picks.csv")
    monkeypatch.setattr(sc, "next_report", lambda *a: INFO)

    def boom(state, **kw):
        raise jev.JevError("down")

    monkeypatch.setattr(jev, "ask", boom)
    with pytest.raises(jev.JevError):
        sc.scan(["AAA"], now=NOW)


def test_scan_refuses_when_yahoo_lookups_mostly_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "LOG", tmp_path / "picks.csv")

    def down(*a):
        raise ConnectionError

    monkeypatch.setattr(sc, "next_report", down)
    with pytest.raises(jev.JevError, match="Yahoo"):                     # an outage must not look like "nobody reports"
        sc.scan(["AAA", "BBB"], now=NOW)


def test_jev_needs_a_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(jev.JevError, match="TYPESAFE_API_KEY"):
        jev.ask("x")


def test_a_report_already_out_is_never_returned(monkeypatch):
    import sys
    import types

    cal = {"Earnings Date": [date(2026, 10, 27)], "Earnings Low": 1, "Earnings High": 2, "Earnings Average": 1.5}
    fake = types.SimpleNamespace(Ticker=lambda t: types.SimpleNamespace(
        calendar=cal, fast_info={"last_price": 10.0}, get_earnings_dates=lambda limit: (_ for _ in ()).throw(ValueError)))
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    assert sc.next_report("AMT", datetime(2026, 10, 27, 16, 20, tzinfo=ET), 7) is None   # 8:00 today is already past
    assert sc.next_report("AMT", datetime(2026, 10, 26, 16, 20, tzinfo=ET), 7) is not None

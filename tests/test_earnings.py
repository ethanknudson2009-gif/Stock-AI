from datetime import date

import pytest

from stock_ai.earnings import jev, scan as sc


def _ans(up, down, beat, conf=0.8):
    return {"beat": {"noul": beat}, "reaction": {"probabilities": {"up": up, "flat": 1 - up - down, "down": down},
                                                "confidence": conf}}


def test_score_prefers_likely_up_and_likely_beat():
    good = sc.score_answer(_ans(0.7, 0.1, 0.9))[-1]
    meh = sc.score_answer(_ans(0.7, 0.1, 0.1))[-1]
    bad = sc.score_answer(_ans(0.1, 0.7, 0.5))[-1]
    assert good > meh > 0 > bad


def test_scan_ranks_and_logs_once_per_day(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "LOG", tmp_path / "picks.csv")
    info = (date(2026, 10, 28), 1.0, 1.2, 1.1, 100.0)
    monkeypatch.setattr(sc, "next_report", lambda t, today, days: info if t != "CCC" else None)
    answers = {"AAA": _ans(0.8, 0.05, 0.9), "BBB": _ans(0.3, 0.4, 0.4)}
    monkeypatch.setattr(jev, "ask", lambda state, **kw: answers["AAA" if "AAA" in state else "BBB"])
    rows = sc.scan(["AAA", "BBB", "CCC"], today=date(2026, 10, 27))
    assert [r["ticker"] for r in rows] == ["AAA", "BBB"]               # CCC isn't reporting -> skipped
    sc.scan(["AAA", "BBB", "CCC"], today=date(2026, 10, 27))
    assert len((tmp_path / "picks.csv").read_text().splitlines()) == 3  # header + 2 rows, not duplicated


def test_scan_raises_if_jev_returns_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "LOG", tmp_path / "picks.csv")
    monkeypatch.setattr(sc, "next_report", lambda *a: (date(2026, 10, 28), 1, 1, 1, 10.0))

    def boom(state, **kw):
        raise jev.JevError("down")

    monkeypatch.setattr(jev, "ask", boom)
    with pytest.raises(jev.JevError):
        sc.scan(["AAA"], today=date(2026, 10, 27))


def test_jev_needs_a_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(jev.JevError, match="TYPESAFE_API_KEY"):
        jev.ask("x")

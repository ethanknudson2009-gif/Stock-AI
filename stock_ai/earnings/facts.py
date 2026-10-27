"""Hard numbers about a company's earnings habits, handed to Jev alongside the headlines.

Everything here looks only at reports that happened BEFORE `now`, so it can't leak the answer for the upcoming one.
  * beat history   -- how often (and by how much) it beat the analyst EPS estimate in recent quarters
  * past reactions -- how the stock moved right after each of those reports
  * expected move  -- what the options market prices in for this report (an at-the-money straddle)
"""

from datetime import datetime, timedelta

import pandas as pd


def beat_stats(past: pd.DataFrame) -> dict | None:
    """`past`: rows with 'EPS Estimate' and 'Reported EPS'. -> {n, beats, avg_surprise_pct}."""
    d = past.dropna(subset=["EPS Estimate", "Reported EPS"])
    if d.empty:
        return None
    est = d["EPS Estimate"].astype(float)
    surprise = (d["Reported EPS"].astype(float) - est) / est.abs().where(est.abs() > 1e-9)
    return {"n": len(d), "beats": int((d["Reported EPS"].astype(float) > est).sum()),
            "avg_surprise_pct": float(surprise.mean() * 100) if surprise.notna().any() else None}


def reaction_moves(closes: pd.Series, report_times: list[datetime]) -> list[float]:
    """Stock move caused by each report, oldest first, as a fraction (+0.03 = +3%).

    Before-open report (before noon): previous close -> that day's close.
    After-close report (noon or later): that day's close -> next day's close.
    """
    days = pd.DatetimeIndex(closes.index).tz_localize(None).normalize()
    c = pd.Series(closes.to_numpy(dtype=float), index=days)
    moves = []
    for ts in sorted(report_times):
        day = pd.Timestamp(ts.date())
        i = c.index.searchsorted(day)                  # first trading day on/after the report date
        if i >= len(c):
            continue
        before_i, after_i = (i, i + 1) if ts.hour >= 12 else (i - 1, i)
        if before_i < 0 or after_i >= len(c):
            continue
        moves.append(float(c.iloc[after_i] / c.iloc[before_i] - 1))
    return moves


def implied_move(calls: pd.DataFrame, puts: pd.DataFrame, price: float) -> float | None:
    """At-the-money straddle price / stock price = the move the options market expects (about +-, as a fraction)."""
    def mid(df):
        row = df.iloc[(df["strike"] - price).abs().argsort().iloc[0]]
        bid, ask, last = float(row.get("bid", 0) or 0), float(row.get("ask", 0) or 0), float(row.get("lastPrice", 0) or 0)
        return float(row["strike"]), (bid + ask) / 2 if bid > 0 and ask > 0 else last
    try:
        (k1, c), (k2, p) = mid(calls), mid(puts)
    except (IndexError, KeyError, ValueError):
        return None
    return (c + p) / price if k1 == k2 and c > 0 and p > 0 and price > 0 else None


def company_facts(ticker: str, now: datetime, report_ts: datetime, price: float, n: int = 8) -> dict:
    """Fetch and compute the three fact groups; any part Yahoo can't supply is left out (None)."""
    import yfinance as yf  # noqa: PLC0415

    t = yf.Ticker(ticker)
    out = {"beats": None, "moves": None, "implied": None}
    try:
        ed = t.get_earnings_dates(limit=n + 6)
        past = ed[[x.to_pydatetime() <= now for x in ed.index]].dropna(subset=["Reported EPS"]).sort_index(ascending=False).head(n)
        out["beats"] = beat_stats(past)
        closes = t.history(period="4y", auto_adjust=True)["Close"]
        out["moves"] = reaction_moves(closes, [x.to_pydatetime() for x in past.index]) or None
    except Exception:  # noqa: BLE001 -- partial facts are fine; Jev is told what is missing
        pass
    try:
        after = report_ts.date() + timedelta(days=1 if report_ts.hour >= 12 else 0)
        exp = next(e for e in t.options if datetime.strptime(e, "%Y-%m-%d").date() >= after)
        chain = t.option_chain(exp)
        out["implied"] = implied_move(chain.calls, chain.puts, price)
    except Exception:  # noqa: BLE001
        pass
    return out


def describe(f: dict) -> str:
    """Plain-English lines for Jev's input. Missing pieces say so instead of being silently dropped."""
    lines = []
    b = f.get("beats")
    if b:
        s = f" (average surprise {b['avg_surprise_pct']:+.1f}%)" if b.get("avg_surprise_pct") is not None else ""
        lines.append(f"Beat history: beat the analyst EPS estimate in {b['beats']} of its last {b['n']} reports{s}.")
    else:
        lines.append("Beat history: not available.")
    m = f.get("moves")
    if m:
        ups = sum(x > 0 for x in m)
        lines.append("Stock move right after its last %d reports (oldest to newest): %s. Up %d of %d times; average size %.1f%%."
                     % (len(m), ", ".join(f"{x:+.1%}" for x in m), ups, len(m), 100 * sum(abs(x) for x in m) / len(m)))
    else:
        lines.append("Past reactions: not available.")
    i = f.get("implied")
    lines.append(f"Options market expects a move of about {i:.1%} (either direction) around this report." if i
                 else "Options-implied move: not available.")
    return "\n".join(lines)

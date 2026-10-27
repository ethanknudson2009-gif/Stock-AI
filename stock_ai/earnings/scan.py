"""Mass earnings scan: who reports soon, what's the news, what does Jev think. Ranked; log-only."""

import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from stock_ai.earnings import facts, jev

LOG = Path(__file__).resolve().parent.parent.parent / "logs" / "earnings_picks.csv"
ET = ZoneInfo("America/New_York")
FIELDS = ["scan_date", "ticker", "report_ts", "price", "p_up", "p_flat", "p_down", "beat", "confidence", "score",
          "hist_beats", "avg_move", "implied_move"]


def next_report(ticker: str, now: datetime, days: int):
    """(report_ts, eps_low, eps_high, eps_avg, price) if `ticker` reports within `days` AFTER `now`, else None.

    report_ts is the exact ET time from Yahoo when it has one (so before-open vs after-close is known); otherwise the
    calendar date at 08:00 (assume before the open -- the cautious guess). A report already out is never returned:
    its results would be in the headlines and Jev would just read the answer.
    """
    import yfinance as yf  # noqa: PLC0415

    t = yf.Ticker(ticker)
    cal = t.calendar or {}                      # raises if Yahoo is down -- scan() counts that as a lookup failure
    ts = None
    try:
        ts = min((x.to_pydatetime() for x in t.get_earnings_dates(limit=8).index if x.to_pydatetime() > now), default=None)
    except Exception:  # noqa: BLE001 -- fall back to the calendar date
        pass
    if ts is None:
        ds = [d for d in cal.get("Earnings Date", []) if datetime.combine(d, time(8), ET) > now]
        ts = datetime.combine(min(ds), time(8), ET) if ds else None
    if ts is None or ts > now + timedelta(days=days):
        return None
    price = float(t.fast_info["last_price"])
    return ts, cal.get("Earnings Low"), cal.get("Earnings High"), cal.get("Earnings Average"), price


def build_state(ticker: str, info: tuple, headlines: list[str], extra: str = "") -> str:
    report, lo, hi, avg, price = info
    report = f"{report:%Y-%m-%d %H:%M} ET"
    news = "\n".join(f"- {h[:120]}" for h in headlines[:5]) or "- (no recent headlines)"   # newest 5, trimmed: tokens cost money
    est = f"Analyst EPS estimate: {avg:.2f} (range {lo} to {hi})." if avg is not None else "Analyst EPS estimate: not available."
    parts = [f"{ticker} reports quarterly earnings on {report}. Last price ${price:.2f}. {est}"]
    if extra:
        parts.append(extra)
    parts.append(f"Recent headlines:\n{news}")
    return "\n".join(parts)


def score_answer(ans: dict) -> tuple[float, float, float, float, float, float]:
    """(p_up, p_flat, p_down, beat, confidence, score). score = P(up) - P(down), nudged by the beat estimate."""
    p = ans["reaction"]["probabilities"]
    beat = ans["beat"]["noul"]
    score = (p.get("up", 0.0) - p.get("down", 0.0)) * (0.5 + 0.5 * beat)
    return p.get("up", 0.0), p.get("flat", 0.0), p.get("down", 0.0), beat, ans["reaction"]["confidence"], score


def scan(universe: list[str], days: int = 7, top: int | None = 10, now: datetime | None = None,
         headlines_for=None, workers: int = 8, save: bool = True) -> list[dict]:
    """Rank the stocks reporting in the next `days` by Jev's view. `headlines_for(ticker) -> [str]` supplies news."""
    now = now or datetime.now(ET)
    today = now.date()
    def lookup(t):
        try:
            return next_report(t, now, days), False
        except Exception:  # noqa: BLE001
            return None, True

    with ThreadPoolExecutor(workers) as pool:
        looked = list(pool.map(lookup, universe))
        if sum(failed for _, failed in looked) > 0.3 * len(universe):
            raise jev.JevError("Yahoo earnings lookups failed for over 30% of the universe; refusing to plan from that")
        found = {t: i for t, (i, _) in zip(universe, looked) if i}

        def one(t):
            try:
                heads = headlines_for(t) if headlines_for else []
                f = facts.company_facts(t, now, found[t][0], found[t][4])
                return t, (jev.ask(build_state(t, found[t], heads, facts.describe(f))), f)
            except Exception:  # noqa: BLE001 -- one bad stock must not sink the scan
                return t, None

        answers = dict(pool.map(one, list(found)))
    if found and not any(answers.values()):
        raise jev.JevError("Jev returned nothing for any stock (key, network or format problem)")
    rows = []
    for t, got in answers.items():
        if not got:
            continue
        ans, f = got
        up, flat, down, beat, conf, score = score_answer(ans)
        rows.append({"scan_date": today.isoformat(), "ticker": t, "report_ts": found[t][0].isoformat(timespec="minutes"),
                     "price": round(found[t][4], 2), "p_up": round(up, 3), "p_flat": round(flat, 3),
                     "p_down": round(down, 3), "beat": round(beat, 3), "confidence": round(conf, 3),
                     "score": round(score, 3),
                     "hist_beats": f"{f['beats']['beats']}/{f['beats']['n']}" if f.get("beats") else "",
                     "avg_move": round(sum(abs(x) for x in f["moves"]) / len(f["moves"]), 4) if f.get("moves") else "",
                     "implied_move": round(f["implied"], 4) if f.get("implied") else ""})
    rows.sort(key=lambda r: -r["score"])
    if save and rows:
        LOG.parent.mkdir(exist_ok=True)
        old = list(csv.DictReader(LOG.open())) if LOG.exists() else []
        old = [r for r in old if r["scan_date"] != today.isoformat()]      # re-running a day replaces that day
        with LOG.open("w", newline="") as f:
            w = csv.DictWriter(f, FIELDS)
            w.writeheader()
            w.writerows(old + rows)
    return rows if top is None else rows[:top]

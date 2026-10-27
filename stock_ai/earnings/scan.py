"""Mass earnings scan: who reports soon, what's the news, what does Jev think. Ranked; log-only."""

import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

from stock_ai.earnings import jev

LOG = Path(__file__).resolve().parent.parent.parent / "logs" / "earnings_picks.csv"
FIELDS = ["scan_date", "ticker", "report_date", "price", "p_up", "p_flat", "p_down", "beat", "confidence", "score"]


def next_report(ticker: str, today: date, days: int):
    """(report_date, eps_low, eps_high, eps_avg, price) if `ticker` reports within `days`, else None."""
    import yfinance as yf  # noqa: PLC0415

    try:
        t = yf.Ticker(ticker)
        cal = t.calendar or {}
        dates = [d for d in cal.get("Earnings Date", []) if today < d <= today + timedelta(days=days)]   # strictly AFTER today: a report already out would leak into the headlines
        if not dates:
            return None
        price = float(t.fast_info["last_price"])
    except Exception:  # noqa: BLE001 -- Yahoo is flaky; a name we can't read is skipped, never guessed
        return None
    return dates[0], cal.get("Earnings Low"), cal.get("Earnings High"), cal.get("Earnings Average"), price


def build_state(ticker: str, info: tuple, headlines: list[str]) -> str:
    report, lo, hi, avg, price = info
    news = "\n".join(f"- {h}" for h in headlines[:8]) or "- (no recent headlines)"
    return (f"{ticker} reports quarterly earnings on {report}. Last price ${price:.2f}. "
            f"Analyst EPS estimate: low {lo}, high {hi}, average {avg}.\nRecent headlines:\n{news}")


def score_answer(ans: dict) -> tuple[float, float, float, float, float, float]:
    """(p_up, p_flat, p_down, beat, confidence, score). score = P(up) - P(down), nudged by the beat estimate."""
    p = ans["reaction"]["probabilities"]
    beat = ans["beat"]["noul"]
    score = (p.get("up", 0.0) - p.get("down", 0.0)) * (0.5 + 0.5 * beat)
    return p.get("up", 0.0), p.get("flat", 0.0), p.get("down", 0.0), beat, ans["reaction"]["confidence"], score


def scan(universe: list[str], days: int = 7, top: int = 10, today: date | None = None,
         headlines_for=None, workers: int = 8, save: bool = True) -> list[dict]:
    """Rank the stocks reporting in the next `days` by Jev's view. `headlines_for(ticker) -> [str]` supplies news."""
    today = today or date.today()
    with ThreadPoolExecutor(workers) as pool:
        found = {t: i for t, i in zip(universe, pool.map(lambda t: next_report(t, today, days), universe)) if i}

        def one(t):
            try:
                heads = headlines_for(t) if headlines_for else []
                return t, jev.ask(build_state(t, found[t], heads))
            except Exception:  # noqa: BLE001 -- one bad stock must not sink the scan
                return t, None

        answers = dict(pool.map(one, list(found)))
    if found and not any(answers.values()):
        raise jev.JevError("Jev returned nothing for any stock (key, network or format problem)")
    rows = []
    for t, ans in answers.items():
        if not ans:
            continue
        up, flat, down, beat, conf, score = score_answer(ans)
        rows.append({"scan_date": today.isoformat(), "ticker": t, "report_date": found[t][0].isoformat(),
                     "price": round(found[t][4], 2), "p_up": round(up, 3), "p_flat": round(flat, 3),
                     "p_down": round(down, 3), "beat": round(beat, 3), "confidence": round(conf, 3),
                     "score": round(score, 3)})
    rows.sort(key=lambda r: -r["score"])
    if save and rows:
        LOG.parent.mkdir(exist_ok=True)
        old = list(csv.DictReader(LOG.open())) if LOG.exists() else []
        old = [r for r in old if r["scan_date"] != today.isoformat()]      # re-running a day replaces that day
        with LOG.open("w", newline="") as f:
            w = csv.DictWriter(f, FIELDS)
            w.writeheader()
            w.writerows(old + rows)
    return rows[:top]

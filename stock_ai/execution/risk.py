"""Risk rules for the paper bot: sector cap, per-position stop-loss, daily loss halt.

Pure functions (no I/O) so they are easy to test. bot.plan_orders applies them; limits live in bot.py.
"""


def apply_sector_cap(ranked: list[str], n: int, max_per_sector: int | None, sectors: dict[str, str]) -> list[str]:
    """Walk `ranked` (best first), keep up to `n` tickers, never more than `max_per_sector` from one sector.

    Tickers with an unknown sector never count against a cap. Names skipped by the cap are replaced by the
    next-best ones from other sectors.
    """
    chosen, count = [], {}
    for t in ranked:
        sec = sectors.get(t)
        if max_per_sector is not None and sec is not None and count.get(sec, 0) >= max_per_sector:
            continue
        chosen.append(t)
        if sec is not None:
            count[sec] = count.get(sec, 0) + 1
        if len(chosen) == n:
            break
    return chosen


def stop_loss_tickers(positions: list[dict], stop_pct: float) -> list[str]:
    """Tickers whose unrealized loss has reached `stop_pct` (e.g. 0.10 = down 10% or more)."""
    return [p["ticker"] for p in positions if p.get("pl_pct") is not None and p["pl_pct"] <= -stop_pct]


def daily_loss_halt(day_pl_pct: float | None, limit_pct: float) -> bool:
    """True when the account is down `limit_pct` or more today — the bot then places no new buys."""
    return day_pl_pct is not None and day_pl_pct <= -limit_pct

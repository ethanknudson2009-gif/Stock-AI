"""Trading-day helpers. All market time is US/Eastern — never naive local time (Pitfall #7)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def now_eastern() -> datetime:
    """Current time in US/Eastern, regardless of the machine's timezone."""
    return datetime.now(tz=EASTERN)


def trading_day_today(now: datetime | None = None) -> date:
    """Return today's Eastern-time trading date.

    `now` may be supplied (tz-aware or naive-UTC) for testing; it is converted to
    Eastern first, so a PT clock at 11:59pm still yields the correct Eastern date.
    """
    if now is None:
        now = now_eastern()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("UTC"))
    return now.astimezone(EASTERN).date()

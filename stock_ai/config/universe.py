"""Default ticker universe: 30 large-cap, highly liquid US equities.

Edit DEFAULT_UNIVERSE to change which tickers the multi-ticker strategy and bot use.

WARNING — survivorship bias: this is a *current* universe snapshot (as of 2026-10).
Backtests over past years are survivorship-biased by construction, because every
company that was delisted, acquired, or fell out of the large-cap set is missing.
Expect backtested returns to look better than they really would have been.
For honest historical research, use a point-in-time index membership source —
out of scope for v1.
"""

DEFAULT_UNIVERSE: list[str] = [
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "ORCL", "ADBE", "CRM", "CSCO",
    # Consumer
    "AMZN", "WMT", "COST", "HD", "MCD", "KO", "PEP", "PG", "DIS", "NFLX",
    # Financials
    "JPM", "BAC", "V", "MA",
    # Healthcare
    "UNH", "JNJ", "ABBV", "MRK",
    # Energy
    "XOM", "CVX",
]

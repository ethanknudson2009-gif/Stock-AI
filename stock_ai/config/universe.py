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


MEGA_CAP_TECH: list[str] = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AVGO", "ORCL", "ADBE", "CRM"]

# Named universes offered in the UI. "Large-cap 30" is DEFAULT_UNIVERSE — a
# hand-picked current snapshot of big US names, not the official S&P 500 top 30
# by index weight.
PRESETS: dict[str, list[str]] = {
    "Mega-cap tech": MEGA_CAP_TECH,
    "Large-cap 30": DEFAULT_UNIVERSE,
}


# Common US tickers offered as autocomplete suggestions (any valid symbol is still accepted).
TICKER_SUGGESTIONS: list[str] = sorted(set(DEFAULT_UNIVERSE + [
    "SPY", "QQQ", "DIA", "IWM", "VOO", "VTI", "TSLA", "AMD", "INTC", "QCOM", "TXN", "MU", "AMAT", "IBM", "NOW",
    "INTU", "PYPL", "UBER", "ABNB", "SHOP", "SNOW", "PLTR", "PANW", "CRWD", "SBUX", "NKE", "TGT", "LOW", "TJX",
    "BKNG", "MDLZ", "PM", "MO", "CL", "KMB", "GS", "MS", "WFC", "C", "AXP", "BLK", "SCHW", "BRK-B", "PFE", "LLY",
    "TMO", "ABT", "DHR", "BMY", "AMGN", "GILD", "CVS", "MDT", "COP", "SLB", "EOG", "OXY", "BA", "CAT", "DE", "GE",
    "HON", "LMT", "RTX", "UPS", "UNP", "FDX", "T", "VZ", "TMUS", "CMCSA", "NEE", "DUK", "SO", "AMT", "PLD", "F", "GM",
]))


# Sector of each default-universe ticker (GICS-style groups), used by the sector-concentration cap.
SECTORS: dict[str, str] = {
    **dict.fromkeys(["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "ADBE", "CRM", "CSCO"], "Technology"),
    **dict.fromkeys(["GOOGL", "META", "NFLX", "DIS"], "Communication"),
    **dict.fromkeys(["AMZN", "HD", "MCD"], "Discretionary"),
    **dict.fromkeys(["WMT", "COST", "KO", "PEP", "PG"], "Staples"),
    **dict.fromkeys(["JPM", "BAC", "V", "MA"], "Financials"),
    **dict.fromkeys(["UNH", "JNJ", "ABBV", "MRK"], "Healthcare"),
    **dict.fromkeys(["XOM", "CVX"], "Energy"),
}

"""Fetch historical OHLCV price data for a ticker."""

import pandas as pd
import yfinance as yf


def fetch_price_history(ticker: str, start: str, end: str | None = None) -> pd.DataFrame:
    """Download daily OHLCV history for `ticker` between `start` and `end`.

    yfinance returns MultiIndex columns like ('Close', 'AAPL') even for a single
    ticker (Pitfall #22). We flatten them to plain names ('Close', ...) so every
    downstream `df["Close"]` is a Series, not a one-column DataFrame.
    """
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No price data returned for ticker '{ticker}'")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index.name = "date"
    return df

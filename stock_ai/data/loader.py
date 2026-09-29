"""Fetch historical OHLCV price data for a ticker."""

import pandas as pd
import yfinance as yf


def fetch_price_history(ticker: str, start: str, end: str | None = None) -> pd.DataFrame:
    """Download daily OHLCV history for `ticker` between `start` and `end`."""
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No price data returned for ticker '{ticker}'")
    df.index.name = "date"
    return df

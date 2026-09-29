"""Technical indicator feature engineering."""

import pandas as pd


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add moving averages, RSI, and daily return columns to price data."""
    out = df.copy()
    out["return_1d"] = out["Close"].pct_change()
    out["sma_10"] = out["Close"].rolling(10).mean()
    out["sma_50"] = out["Close"].rolling(50).mean()
    out["rsi_14"] = _rsi(out["Close"], period=14)
    return out.dropna()


def _rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

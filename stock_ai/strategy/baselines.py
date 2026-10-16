"""Simple benchmark strategies the model must beat to be worth anything."""

import pandas as pd

from stock_ai.strategy.ranker import top_n


def buy_hold_positions(df: pd.DataFrame) -> pd.Series:
    """Always long."""
    return pd.Series(1, index=df.index, name="position")


def sma_crossover_positions(df: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.Series:
    """Long while the fast moving average is above the slow one (classic 50/200 'golden cross').

    Uses only prices up to each day; the backtester shifts positions one day.
    """
    close = df["Close"]
    fast_ma = close.rolling(fast).mean()
    slow_ma = close.rolling(slow, min_periods=fast).mean()
    return (fast_ma > slow_ma).astype(int).rename("position")


def momentum_weights(returns: pd.DataFrame, n: int, lookback: int = 126) -> pd.DataFrame:
    """Cross-sectional momentum: each day hold the top-N by trailing `lookback`-day return."""
    trailing = (1 + returns.fillna(0)).rolling(lookback).apply(lambda r: r.prod(), raw=True) - 1
    trailing = trailing.where(returns.notna())
    return top_n(trailing, n)

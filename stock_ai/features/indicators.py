"""Technical indicator feature engineering.

All features are deliberately *stationary* (scale-free): returns, ratios, and
bounded oscillators — never raw price levels. A tree trained on 2015 prices
must still make sense on 2026 prices, so absolute dollar features (e.g. a raw
50-day average) are avoided because their learned split points don't transfer
across price regimes.
"""

import pandas as pd


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add stationary momentum, trend-ratio, volatility, and RSI features."""
    out = df.copy()
    close = out["Close"]

    # Momentum at several horizons (all scale-free percentage changes).
    out["return_1d"] = close.pct_change()
    out["return_5d"] = close.pct_change(5)
    out["return_10d"] = close.pct_change(10)
    out["return_20d"] = close.pct_change(20)

    # Trend as ratios, not raw price: "how far above its own average" transfers
    # across price regimes; a raw SMA in dollars does not.
    sma_10 = close.rolling(10).mean()
    sma_50 = close.rolling(50).mean()
    out["price_to_sma10"] = close / sma_10
    out["sma10_to_sma50"] = sma_10 / sma_50

    # Volatility regime and a bounded oscillator.
    out["volatility_20d"] = out["return_1d"].rolling(20).std()
    out["rsi_14"] = _rsi(close, period=14)

    return out.dropna()


def _rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

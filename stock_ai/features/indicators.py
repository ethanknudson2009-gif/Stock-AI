"""Technical indicator feature engineering.

All features are deliberately *stationary* (scale-free): returns, ratios, and
bounded oscillators — never raw price levels. A tree trained on 2015 prices
must still make sense on 2026 prices, so absolute dollar features (e.g. a raw
50-day average) are avoided because their learned split points don't transfer
across price regimes.
"""

import pandas as pd


def add_features(df: pd.DataFrame, market_close: pd.Series | None = None) -> pd.DataFrame:
    """Add stationary momentum, trend, volatility, volume, RSI and regime features.

    `market_close` (e.g. SPY closes) enables the market-regime feature; without
    it the feature is a neutral constant 1.0, which a tree model simply ignores.
    """
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

    # Volume surprise: today's volume vs. its recent norm (0 when volume is missing).
    if "Volume" in out.columns:
        vol = out["Volume"].astype(float)
        std = vol.rolling(20).std().replace(0, float("nan"))
        out["volume_z_20"] = ((vol - vol.rolling(20).mean()) / std).fillna(0.0)
    else:
        out["volume_z_20"] = 0.0

    # Volatility regime: is recent vol elevated vs. its own ~5-month norm? Also
    # how far the stock sits below its 6-month high.
    out["vol_ratio_20_100"] = out["volatility_20d"] / out["volatility_20d"].rolling(100).mean()
    out["drawdown_120"] = close / close.rolling(120).max()

    # Regimes: the stock's long-term trend, and the broad market's.
    out["trend_regime_200"] = close / close.rolling(200).mean()
    if market_close is not None:
        mkt = market_close.reindex(out.index).ffill()
        out["market_regime"] = mkt / mkt.rolling(200, min_periods=150).mean()
        out["spy_close"] = mkt  # not a model input; used to build excess-return labels
    else:
        out["market_regime"] = 1.0

    return out.dropna()


def _rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


RANK_COLUMNS = ["rank_return_20d", "rank_volatility_20d", "rank_return_5d"]


def add_cross_sectional_ranks(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add each stock's percentile rank (0-1) among its peers each day for 20d/5d momentum and volatility.

    Needs several tickers at once, so it only works where a universe is loaded
    together (the harness, the Portfolio page) — not on a single-ticker page.
    """
    out = {t: df.copy() for t, df in frames.items()}
    for src, dst in (("return_20d", "rank_return_20d"), ("volatility_20d", "rank_volatility_20d"),
                     ("return_5d", "rank_return_5d")):
        ranks = pd.DataFrame({t: df[src] for t, df in frames.items()}).rank(axis=1, pct=True)
        for t in out:
            out[t][dst] = ranks[t].reindex(out[t].index).fillna(0.5)
    return out

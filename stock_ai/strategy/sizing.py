"""Position sizing: scale a long/flat signal by how volatile the stock is right now."""

import pandas as pd


def vol_target_positions(
    signal: pd.Series, daily_vol: pd.Series, target_annual_vol: float = 0.15, cap: float = 1.0
) -> pd.Series:
    """Hold `signal` at a size that aims for `target_annual_vol` — calm stocks get a full
    position, wild ones a smaller one. Capped at `cap` (1.0 = no leverage)."""
    ann = (daily_vol * 252 ** 0.5).replace(0, float("nan"))
    size = (target_annual_vol / ann).clip(upper=cap).fillna(cap)
    return (signal * size).rename("position")

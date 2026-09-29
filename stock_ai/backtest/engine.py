"""Simple long/flat backtester: apply positions to returns and report performance."""

import pandas as pd


def run_backtest(df: pd.DataFrame, positions: pd.Series) -> dict:
    """Apply `positions` (shifted by 1 day to avoid lookahead) to daily returns."""
    strategy_returns = df["return_1d"] * positions.shift(1).fillna(0)
    cumulative = (1 + strategy_returns).cumprod()
    buy_hold = (1 + df["return_1d"]).cumprod()

    total_return = cumulative.iloc[-1] - 1
    buy_hold_return = buy_hold.iloc[-1] - 1
    sharpe = _sharpe_ratio(strategy_returns)

    return {
        "total_return": total_return,
        "buy_hold_return": buy_hold_return,
        "sharpe_ratio": sharpe,
        "cumulative_returns": cumulative,
    }


def _sharpe_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    if returns.std() == 0:
        return 0.0
    return (returns.mean() / returns.std()) * (periods_per_year ** 0.5)

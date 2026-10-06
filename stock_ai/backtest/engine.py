"""Simple long/flat backtester: apply positions to returns and report performance."""

import pandas as pd


def run_backtest(
    df: pd.DataFrame,
    positions: pd.Series,
    cost_bps: float = 10.0,
) -> dict:
    """Apply `positions` (shifted by 1 day to avoid lookahead) to daily returns.

    `cost_bps` deducts a per-trade cost in basis points (1 bp = 0.01%) each
    time the position changes. 10 bps (~0.1%) is a reasonable blended estimate
    of commission + slippage for a liquid US equity on a retail account; set
    to 0 to disable.
    """
    shifted_positions = positions.shift(1).fillna(0)
    gross_returns = df["return_1d"] * shifted_positions

    trades = shifted_positions.diff().abs().fillna(shifted_positions.abs())
    cost_per_trade = cost_bps / 10_000
    costs = trades * cost_per_trade

    strategy_returns = gross_returns - costs
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
        "n_trades": int(trades.sum()),
        "cost_bps": cost_bps,
    }


def _sharpe_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    if returns.std() == 0:
        return 0.0
    return (returns.mean() / returns.std()) * (periods_per_year ** 0.5)

import numpy as np
import pandas as pd

from stock_ai.backtest.engine import run_backtest


def _flat_market(n: int = 100, daily_return: float = 0.001) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame({"return_1d": [daily_return] * n}, index=dates)


def test_costs_reduce_return_when_trading():
    df = _flat_market()
    positions = pd.Series([i % 2 for i in range(len(df))], index=df.index)

    no_cost = run_backtest(df, positions, cost_bps=0)
    with_cost = run_backtest(df, positions, cost_bps=10)

    assert with_cost["total_return"] < no_cost["total_return"]
    assert with_cost["n_trades"] > 0


def test_zero_trades_means_zero_cost_impact():
    df = _flat_market()
    always_long = pd.Series([1] * len(df), index=df.index)

    no_cost = run_backtest(df, always_long, cost_bps=0)
    with_cost = run_backtest(df, always_long, cost_bps=100)

    assert with_cost["n_trades"] == 1, "only the initial entry counts as a trade"
    gap = no_cost["total_return"] - with_cost["total_return"]
    assert 0.009 < gap < 0.013, (
        f"single 100-bps entry should cost ~1% (compounded); got {gap:.4%}"
    )

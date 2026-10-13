"""Tests for cross-sectional ranking and the portfolio-level multi-ticker backtest."""

import numpy as np
import pandas as pd

from stock_ai.backtest.multi_engine import (
    align_series,
    canonical_calendar,
    run_multi_backtest,
)
from stock_ai.strategy.ranker import top_n


def _random_matrix(n_days=3000, n_tickers=25, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-03", periods=n_days, freq="B")
    cols = [f"T{i:02d}" for i in range(n_tickers)]
    returns = pd.DataFrame(rng.normal(0, 0.01, size=(n_days, n_tickers)), index=idx, columns=cols)
    proba = pd.DataFrame(rng.uniform(0, 1, size=(n_days, n_tickers)), index=idx, columns=cols)
    return returns, proba


def test_top_n_selects_exactly_n_equal_weights():
    proba = pd.DataFrame(
        [[0.9, 0.1, 0.5, 0.7]],
        columns=["A", "B", "C", "D"],
        index=pd.to_datetime(["2024-01-02"]),
    )
    w = top_n(proba, 2)
    assert w.loc["2024-01-02", "A"] == 0.5  # 1/2
    assert w.loc["2024-01-02", "D"] == 0.5
    assert w.loc["2024-01-02", "B"] == 0.0
    assert w.loc["2024-01-02", "C"] == 0.0
    assert abs(w.sum(axis=1).iloc[0] - 1.0) < 1e-9


def test_top_n_never_selects_nan():
    proba = pd.DataFrame(
        [[np.nan, 0.2, 0.3]],
        columns=["A", "B", "C"],
        index=pd.to_datetime(["2024-01-02"]),
    )
    w = top_n(proba, 2)
    assert w.loc["2024-01-02", "A"] == 0.0


def test_portfolio_sharpe_near_zero_on_random_signals():
    """Random signals over a long window give a portfolio Sharpe near 0 (no edge).

    Over 3000 sessions the annualized-Sharpe sampling error is ~0.3, so a |value|
    under 1.0 confirms the strategy finds no real edge in pure noise.
    """
    returns, proba = _random_matrix(seed=42)
    weights = top_n(proba, 5)
    result = run_multi_backtest(returns, weights, cost_bps=0)
    assert abs(result["portfolio_sharpe"]) < 1.0


def test_portfolio_sharpe_is_not_average_of_per_ticker_sharpes():
    """Pitfall #3 guard: portfolio Sharpe must come from the combined return series.

    Build a universe where every ticker has a strong positive mean but the
    tickers are negatively correlated in pairs, so a true equal-weight portfolio
    cancels most variance and earns a FAR higher Sharpe than the average of the
    individual per-ticker Sharpes. If the code mistakenly averaged per-ticker
    Sharpes, the two numbers would be ~equal.
    """
    from stock_ai.backtest.engine import _sharpe_ratio

    idx = pd.date_range("2015-01-02", periods=2000, freq="B")
    rng = np.random.default_rng(0)
    base = rng.normal(0, 0.02, size=len(idx))  # shared noise, cancels in pairs
    cols, data = [], {}
    drift = 0.0005
    for i in range(10):
        a = drift + base + rng.normal(0, 0.002, len(idx))
        b = drift - base + rng.normal(0, 0.002, len(idx))
        data[f"A{i}"], data[f"B{i}"] = a, b
        cols += [f"A{i}", f"B{i}"]
    returns = pd.DataFrame(data, index=idx, columns=cols)

    # Hold everything equal-weight, every day.
    weights = pd.DataFrame(1.0 / len(cols), index=idx, columns=cols)
    portfolio_sharpe = run_multi_backtest(returns, weights, cost_bps=0)["portfolio_sharpe"]

    avg_per_ticker_sharpe = float(np.mean([_sharpe_ratio(returns[c]) for c in cols]))

    # True diversification: portfolio Sharpe is much higher than the per-ticker avg.
    assert portfolio_sharpe > avg_per_ticker_sharpe * 2


def test_portfolio_return_series_has_no_unexplained_nans():
    returns, proba = _random_matrix(seed=1)
    weights = top_n(proba, 5)
    result = run_multi_backtest(returns, weights, cost_bps=10)
    assert not result["portfolio_returns"].isna().any()
    assert result["n_days"] == len(returns)


def test_costs_reduce_portfolio_return():
    returns, proba = _random_matrix(seed=7)
    weights = top_n(proba, 5)
    free = run_multi_backtest(returns, weights, cost_bps=0)["total_return"]
    costly = run_multi_backtest(returns, weights, cost_bps=50)["total_return"]
    assert costly < free


def test_canonical_calendar_is_union_and_align_reindexes():
    idx_a = pd.date_range("2024-01-01", periods=5, freq="B")
    idx_b = pd.date_range("2024-01-03", periods=5, freq="B")
    frames = {"A": pd.DataFrame({"x": range(5)}, index=idx_a),
              "B": pd.DataFrame({"x": range(5)}, index=idx_b)}
    cal = canonical_calendar(frames)
    assert cal.equals(idx_a.union(idx_b))
    aligned = align_series({"A": frames["A"]["x"], "B": frames["B"]["x"]}, cal, max_ffill_gap=0)
    assert list(aligned.columns) == ["A", "B"]
    assert aligned.index.equals(cal)

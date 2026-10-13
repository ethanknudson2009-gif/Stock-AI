"""Multi-ticker cross-sectional backtest.

Combines per-ticker legs into ONE portfolio daily-return series and computes a
portfolio-level Sharpe on that series — never an average of per-ticker Sharpes
(Pitfall #3). All tickers are first reindexed onto a single canonical trading-day
calendar so returns at time t line up across tickers (Pitfall #5).
"""

import pandas as pd

from stock_ai.backtest.engine import _max_drawdown, _sharpe_ratio


def canonical_calendar(frames: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    """Sorted union of every ticker's dates — the reference trading-day index.

    yfinance returns real NYSE sessions per ticker, so their union is a sound
    calendar without an external market-calendar dependency.
    """
    index = pd.DatetimeIndex([])
    for df in frames.values():
        index = index.union(df.index)
    return index.sort_values()


def align_series(
    series_by_ticker: dict[str, pd.Series],
    calendar: pd.DatetimeIndex,
    max_ffill_gap: int = 2,
) -> pd.DataFrame:
    """Reindex each ticker's series onto `calendar`, forward-filling only tiny gaps.

    Gaps longer than `max_ffill_gap` sessions (a late listing or a long halt)
    stay NaN rather than fabricating prices. Returns a date×ticker DataFrame.
    """
    aligned = {}
    for ticker, series in series_by_ticker.items():
        reindexed = series.reindex(calendar)
        if max_ffill_gap > 0:
            reindexed = reindexed.ffill(limit=max_ffill_gap)
        aligned[ticker] = reindexed
    return pd.DataFrame(aligned, index=calendar)


def run_multi_backtest(
    returns: pd.DataFrame,
    weights: pd.DataFrame,
    cost_bps: float = 10.0,
) -> dict:
    """Backtest a daily-rebalanced equal-weight portfolio.

    `returns` and `weights` are date×ticker frames on the same calendar.
    Weights are shifted one day (enter the session after the signal) to avoid
    lookahead. Portfolio daily return = sum_ticker(weight_{t-1} * return_t),
    minus turnover cost. Benchmark = equal-weight-all, daily rebalanced.
    """
    weights = weights.reindex_like(returns).fillna(0.0)
    returns = returns.fillna(0.0)

    held = weights.shift(1).fillna(0.0)
    gross = (held * returns).sum(axis=1)

    turnover = held.diff().abs().sum(axis=1)
    turnover.iloc[0] = held.iloc[0].abs().sum()
    costs = turnover * (cost_bps / 10_000)

    portfolio = gross - costs
    cumulative = (1 + portfolio).cumprod()

    benchmark = returns.mean(axis=1)
    benchmark_cumulative = (1 + benchmark).cumprod()

    return {
        "total_return": float(cumulative.iloc[-1] - 1),
        "buy_hold_return": float(benchmark_cumulative.iloc[-1] - 1),
        "portfolio_sharpe": _sharpe_ratio(portfolio),
        "max_drawdown": _max_drawdown(cumulative),
        "n_days": int(len(portfolio)),
        "avg_positions": float((held > 0).sum(axis=1).mean()),
        "cost_bps": cost_bps,
        "cumulative_returns": cumulative,
        "portfolio_returns": portfolio,
    }


def backtest_universe(
    frames: dict[str, pd.DataFrame],
    backend_factory,
    top_n_count: int,
    cost_bps: float = 10.0,
):
    """Train one SignalBackend per ticker, then run a top-N cross-sectional backtest.

    `frames` maps ticker -> featured price DataFrame (output of add_features).
    `backend_factory()` returns a fresh, unfitted SignalBackend each call.
    Each ticker is trained on its own chronological split; signals and returns
    come from the held-out test slice only (honest OOS). Returns
    (results_dict, proba_matrix, returns_matrix). Tickers whose training fails
    (too little data) are skipped.
    """
    from stock_ai.models.classifier import train_model
    from stock_ai.strategy.ranker import top_n
    from stock_ai.strategy.signal import FEATURE_COLUMNS

    proba_by_ticker: dict[str, pd.Series] = {}
    returns_by_ticker: dict[str, pd.Series] = {}

    for ticker, df in frames.items():
        try:
            model, _accuracy, _train_df, test_df = train_model(df)
        except (ValueError, IndexError):
            continue
        if test_df.empty:
            continue
        backend = backend_factory()
        backend._model = model  # reuse the just-fitted model without retraining
        proba_by_ticker[ticker] = backend.predict_proba_up(test_df[FEATURE_COLUMNS])
        returns_by_ticker[ticker] = test_df["return_1d"]

    if not proba_by_ticker:
        raise ValueError("No tickers produced a usable backtest leg")

    calendar = canonical_calendar(
        {t: s.to_frame() for t, s in proba_by_ticker.items()}
    )
    proba_matrix = align_series(proba_by_ticker, calendar, max_ffill_gap=0)
    returns_matrix = align_series(returns_by_ticker, calendar, max_ffill_gap=0)

    weights = top_n(proba_matrix, top_n_count)
    results = run_multi_backtest(returns_matrix, weights, cost_bps=cost_bps)
    return results, proba_matrix, returns_matrix

"""Cross-sectional selection: each day, pick the top-N tickers by predicted probability."""

import pandas as pd


def top_n(predictions: pd.DataFrame, n: int) -> pd.DataFrame:
    """Return an equal-weight selection matrix from a per-day prediction matrix.

    `predictions` is indexed by date with one column per ticker, holding each
    ticker's predicted probability of going up that day. For each row (day),
    the `n` highest-probability tickers get weight `1/n`; everyone else gets 0.
    NaN predictions (e.g. a ticker not yet listed) are never selected. If fewer
    than `n` tickers have a value on a day, the available ones still split 1/n
    each (the portfolio holds some cash that day) — this keeps position sizing
    honest rather than over-concentrating into whatever few names exist.
    """
    if n <= 0:
        raise ValueError("n must be a positive integer")

    weights = pd.DataFrame(0.0, index=predictions.index, columns=predictions.columns)
    # Rank each row descending; rank 1..n are selected. NaNs get no rank → not selected.
    ranks = predictions.rank(axis=1, ascending=False, method="first", na_option="keep")
    selected = ranks <= n
    weights[selected] = 1.0 / n
    return weights

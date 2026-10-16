"""Classification diagnostics for out-of-sample predictions."""

import numpy as np
import pandas as pd


def classification_stats(proba: pd.Series, labels: pd.Series, threshold: float = 0.5) -> dict:
    """Accuracy, precision, recall, confusion matrix, Brier score and base rate.

    `proba` is P(up); `labels` are the realized 0/1 outcomes on the same index.
    Precision answers "when the model said up, how often was it right?" and
    recall "of the real up-moves, how many did it catch?". The base rate (share
    of up labels) is the accuracy of always guessing "up" — the bar to beat.
    """
    y = labels.reindex(proba.index).dropna().astype(int)
    p = proba.loc[y.index]
    pred = (p > threshold).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    n = tp + fp + fn + tn
    return {
        "n": n,
        "accuracy": (tp + tn) / n if n else 0.0,
        "precision": tp / (tp + fp) if (tp + fp) else 0.0,
        "recall": tp / (tp + fn) if (tp + fn) else 0.0,
        "base_rate": float(y.mean()) if n else 0.0,
        "brier": float(((p - y) ** 2).mean()) if n else 0.0,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def base_rate_brier(labels: pd.Series, horizon: int = 5) -> float:
    """Brier score of the base-rate predictor: always say P(up) = the up-frequency seen so far.

    The running frequency is lagged by `horizon` days (only labels already resolved),
    so it is something you could really have known. A model whose Brier is not below
    this has no reliable edge over just quoting the historical up-frequency.
    """
    y = labels.dropna().astype(float)
    if y.empty:
        return 0.0
    prior = y.expanding().mean().shift(horizon).fillna(0.5)
    return float(((prior - y) ** 2).mean())


def edge_check(proba: pd.Series, labels: pd.Series, horizon: int = 5) -> dict:
    """Minimum-edge rule: does the model's out-of-sample Brier beat the base-rate predictor's?

    If not, the app must say "no reliable edge" rather than issue a Buy. `margin` is
    base minus model Brier (positive = the model is better calibrated than quoting
    the historical up-frequency).
    """
    y = labels.reindex(proba.index).dropna().astype(float)
    p = proba.loc[y.index]
    brier = float(((p - y) ** 2).mean()) if len(y) else 1.0
    base = base_rate_brier(y, horizon)
    return {"brier": brier, "base_brier": base, "margin": base - brier,
            "has_edge": len(y) > 0 and brier < base, "base_rate": float(y.mean()) if len(y) else 0.5}


def block_bootstrap_sharpe(returns: pd.Series, n_boot: int = 500, block: int = 20,
                           seed: int = 0, periods: int = 252) -> tuple[float, float]:
    """95% confidence interval for the annualized Sharpe via a moving-block bootstrap.

    Resamples runs of `block` consecutive days (keeps volatility clustering and
    autocorrelation) and recomputes the Sharpe each time. Returns (low, high).
    """
    r = returns.dropna().to_numpy()
    n = len(r)
    if n < 2 * block:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    n_blocks = -(-n // block)
    starts = rng.integers(0, n - block + 1, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)).reshape(n_boot, -1)[:, :n]
    samples = r[idx]
    sd = samples.std(axis=1)
    sharpe = np.where(sd > 0, samples.mean(axis=1) / np.where(sd > 0, sd, 1) * periods ** 0.5, 0.0)
    lo, hi = np.percentile(sharpe, [2.5, 97.5])
    return float(lo), float(hi)

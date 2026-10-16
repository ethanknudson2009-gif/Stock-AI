"""Classification diagnostics for out-of-sample predictions."""

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

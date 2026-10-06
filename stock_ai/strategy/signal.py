"""Turn model predictions into long/flat trade signals."""

import pandas as pd

from stock_ai.models.classifier import FEATURE_COLUMNS


def generate_signals(
    model,
    df: pd.DataFrame,
    threshold: float = 0.5,
) -> pd.Series:
    """Return a series of 1 (long) / 0 (flat) positions for each row.

    Goes long only when the model's predicted probability of an "up" day
    exceeds `threshold`. The default 0.5 reproduces the old argmax behavior
    (trade on every prediction); raise it (e.g. 0.55, 0.60) to only trade
    high-conviction signals and avoid churning on near-coin-flip predictions.
    """
    proba_up = model.predict_proba(df[FEATURE_COLUMNS])[:, 1]
    positions = (proba_up > threshold).astype(int)
    return pd.Series(positions, index=df.index, name="position")

"""Turn model predictions into long/flat trade signals."""

import pandas as pd

from stock_ai.models.classifier import FEATURE_COLUMNS


def generate_signals(model, df: pd.DataFrame) -> pd.Series:
    """Return a series of 1 (long) / 0 (flat) positions for each row."""
    predictions = model.predict(df[FEATURE_COLUMNS])
    return pd.Series(predictions, index=df.index, name="position")

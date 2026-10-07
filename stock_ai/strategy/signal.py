"""Turn SignalBackend predictions into long/flat trade signals."""

import pandas as pd

from stock_ai.models.base import SignalBackend
from stock_ai.models.classifier import FEATURE_COLUMNS


def generate_signals(backend: SignalBackend, df: pd.DataFrame, threshold: float = 0.5) -> pd.Series:
    """Return a series of 1 (long) / 0 (flat) positions for each row of `df`.

    Goes long only when `backend.predict_proba_up` exceeds `threshold`. The
    default 0.5 reproduces the old argmax behavior (trade on every prediction);
    raise it (e.g. 0.55, 0.60) to only trade high-conviction signals and avoid
    churning on near-coin-flip predictions.
    """
    proba_up = backend.predict_proba_up(df[FEATURE_COLUMNS])
    positions = (proba_up > threshold).astype(int)
    return pd.Series(positions.values, index=df.index, name="position")

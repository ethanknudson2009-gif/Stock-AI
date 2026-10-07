"""Structural Protocol every signal classifier (RandomForest, Jev, …) must satisfy."""

from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class SignalBackend(Protocol):
    """Common contract: a backend has a `name`, trains via `fit`, and emits up-probabilities via `predict_proba_up`."""

    name: str

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Fit the backend on labelled features `X` and binary labels `y`."""
        ...

    def predict_proba_up(self, X: pd.DataFrame) -> pd.Series:
        """Return probability of an "up" day for each row of `X`, aligned to `X.index`."""
        ...

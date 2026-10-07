"""RandomForest signal backend: wraps scikit-learn's RandomForestClassifier behind the SignalBackend Protocol."""

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from stock_ai.models.base import SignalBackend  # noqa: F401 — imported for conformance intent


class RandomForestBackend:
    """SignalBackend wrapping a scikit-learn RandomForestClassifier."""

    name: str = "random_forest"

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 5,
        random_state: int = 42,
    ) -> None:
        """Construct with the same hyperparameters as the pre-refactor classifier."""
        self._model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
        )

    @classmethod
    def from_fitted(cls, model: RandomForestClassifier) -> "RandomForestBackend":
        """Wrap an already-fitted sklearn model without retraining — preserves RNG state for byte-identical output."""
        instance = cls.__new__(cls)
        instance._model = model
        return instance

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Fit the underlying RandomForestClassifier on `X` and `y`."""
        self._model.fit(X, y)

    def predict_proba_up(self, X: pd.DataFrame) -> pd.Series:
        """Return probability of class 1 (up) for each row of `X`, aligned to `X.index`."""
        proba = self._model.predict_proba(X)[:, 1]
        return pd.Series(proba, index=X.index, name="proba_up")

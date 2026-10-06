import numpy as np
import pandas as pd

from stock_ai.models.classifier import FEATURE_COLUMNS
from stock_ai.strategy.signal import generate_signals


class _StubModel:
    """Deterministic probability-returning stub so threshold logic can be tested in isolation."""

    def __init__(self, probas_up):
        self._probas = np.asarray(probas_up)

    def predict_proba(self, X):
        return np.column_stack([1 - self._probas, self._probas])


def _frame(n: int) -> pd.DataFrame:
    data = {col: np.zeros(n) for col in FEATURE_COLUMNS}
    return pd.DataFrame(data, index=pd.date_range("2020-01-01", periods=n, freq="B"))


def test_higher_threshold_reduces_trade_frequency():
    probas = [0.52, 0.48, 0.65, 0.51, 0.70, 0.49, 0.58, 0.50]
    model = _StubModel(probas)
    df = _frame(len(probas))

    low = generate_signals(model, df, threshold=0.5)
    high = generate_signals(model, df, threshold=0.60)

    assert low.sum() == 5, "at 0.50 every proba > 0.5 goes long"
    assert high.sum() == 2, "at 0.60 only 0.65 and 0.70 go long"
    assert high.sum() < low.sum()


def test_threshold_at_zero_is_always_long():
    model = _StubModel([0.3, 0.4, 0.5, 0.6])
    df = _frame(4)
    positions = generate_signals(model, df, threshold=0.0)
    assert (positions == 1).all()

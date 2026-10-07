"""Conformance tests for RandomForestBackend against the SignalBackend Protocol."""

import numpy as np
import pandas as pd
import pytest

from stock_ai.models.base import SignalBackend
from stock_ai.models.classifier import FEATURE_COLUMNS
from stock_ai.models.rf_backend import RandomForestBackend


def _synthetic_frame(n: int = 200, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2020-01-01", periods=n, freq="B")
    X = pd.DataFrame(
        {col: rng.standard_normal(n) for col in FEATURE_COLUMNS},
        index=index,
    )
    y = pd.Series(rng.integers(0, 2, size=n), index=index, name="label")
    return X, y


def test_rf_backend_conforms_to_protocol():
    assert isinstance(RandomForestBackend(), SignalBackend)


def test_rf_backend_name_is_random_forest():
    assert RandomForestBackend().name == "random_forest"


def test_rf_backend_fit_then_predict_returns_aligned_series():
    X, y = _synthetic_frame(n=200)
    backend = RandomForestBackend()
    backend.fit(X, y)

    sample = X.tail(10)
    out = backend.predict_proba_up(sample)

    assert isinstance(out, pd.Series)
    assert list(out.index) == list(sample.index)
    assert out.dtype == float
    assert ((out >= 0.0) & (out <= 1.0)).all()


def test_rf_backend_predict_matches_underlying_sklearn():
    X, y = _synthetic_frame(n=200)
    backend = RandomForestBackend()
    backend.fit(X, y)

    expected = backend._model.predict_proba(X)[:, 1]
    got = backend.predict_proba_up(X).to_numpy()
    np.testing.assert_array_equal(got, expected)


def test_rf_backend_predict_before_fit_raises():
    X, _ = _synthetic_frame(n=10)
    backend = RandomForestBackend()
    with pytest.raises(Exception):
        backend.predict_proba_up(X)

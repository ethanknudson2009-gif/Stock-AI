import numpy as np
import pandas as pd

from stock_ai.features.indicators import add_features
from stock_ai.models.classifier import train_model


def _synthetic_prices(n: int = 400, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    returns = rng.normal(loc=0.0005, scale=0.01, size=n)
    prices = 100 * np.exp(np.cumsum(returns))
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame({"Close": prices}, index=dates)


def test_train_test_split_is_chronological_and_disjoint():
    df = add_features(_synthetic_prices())
    _, _, train_df, test_df = train_model(df)

    assert len(train_df) > 0 and len(test_df) > 0
    assert train_df.index.intersection(test_df.index).empty, (
        "train and test must not share rows — backtest would be in-sample"
    )
    assert train_df.index.max() < test_df.index.min(), (
        "test set must come strictly after train set (no shuffling)"
    )


def test_walk_forward_predict_is_forward_only_and_sized():
    from stock_ai.models.classifier import walk_forward_predict

    df = add_features(_synthetic_prices(n=800))
    proba, accuracy = walk_forward_predict(df, n_splits=5)

    # Probabilities are in [0, 1] and cover the post-warmup tail only.
    assert proba.between(0, 1).all()
    assert 0.0 <= accuracy <= 1.0
    labeled_len = len(df.dropna())
    assert 0 < len(proba) < labeled_len  # a warm-up portion is never predicted
    assert proba.index.is_monotonic_increasing

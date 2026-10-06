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

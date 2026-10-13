import pandas as pd

from stock_ai.features.indicators import add_features
from stock_ai.models.classifier import FEATURE_COLUMNS


def test_add_features_adds_expected_columns():
    df = pd.DataFrame({"Close": [float(i) for i in range(1, 101)]})
    result = add_features(df)

    for col in FEATURE_COLUMNS:
        assert col in result.columns
    assert not result.empty


def test_features_are_stationary_not_raw_price():
    """Trend features must be scale-free ratios, never raw price levels.

    Double the price series: a ratio feature is unchanged, a raw-price feature
    would double. This guards the regime-transfer fix.
    """
    base = pd.DataFrame({"Close": [100 + i for i in range(120)]}, dtype=float)
    scaled = pd.DataFrame({"Close": [2 * (100 + i) for i in range(120)]}, dtype=float)

    a = add_features(base).iloc[-1]
    b = add_features(scaled).iloc[-1]

    for col in ["price_to_sma10", "sma10_to_sma50"]:
        assert abs(a[col] - b[col]) < 1e-6, f"{col} must be scale-invariant"

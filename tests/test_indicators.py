import pandas as pd

from stock_ai.features.indicators import add_features


def test_add_features_adds_expected_columns():
    df = pd.DataFrame({
        "Close": [float(i) for i in range(1, 61)],
    })
    result = add_features(df)

    for col in ["return_1d", "sma_10", "sma_50", "rsi_14"]:
        assert col in result.columns
    assert not result.empty

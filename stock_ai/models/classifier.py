"""Train a model to predict next-day price direction (up/down)."""

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

FEATURE_COLUMNS = ["return_1d", "sma_10", "sma_50", "rsi_14"]


def build_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Label each row 1 if next day's close is higher, else 0."""
    out = df.copy()
    out["label"] = (out["Close"].shift(-1) > out["Close"]).astype(int)
    return out.dropna()


def train_model(
    df: pd.DataFrame,
) -> tuple[RandomForestClassifier, float, pd.DataFrame, pd.DataFrame]:
    """Train a RandomForest and return (model, test_accuracy, train_df, test_df).

    The split is chronological (shuffle=False) so test_df is strictly after
    train_df — required for honest out-of-sample backtesting.
    """
    labeled = build_labels(df)
    X = labeled[FEATURE_COLUMNS]
    y = labeled["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    model = RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42)
    model.fit(X_train, y_train)
    accuracy = model.score(X_test, y_test)

    train_df = labeled.loc[X_train.index]
    test_df = labeled.loc[X_test.index]
    return model, accuracy, train_df, test_df

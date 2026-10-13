"""Train a model to predict near-term price direction, with walk-forward evaluation."""

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

FEATURE_COLUMNS = [
    "return_1d",
    "return_5d",
    "return_10d",
    "return_20d",
    "price_to_sma10",
    "sma10_to_sma50",
    "volatility_20d",
    "rsi_14",
]

# Predict direction over this many trading days ahead, not just tomorrow. A
# multi-day horizon has a better signal-to-noise ratio than next-day direction,
# which is almost pure coin-flip.
LABEL_HORIZON = 5


def build_labels(df: pd.DataFrame, horizon: int = LABEL_HORIZON) -> pd.DataFrame:
    """Label each row 1 if the close `horizon` days later is higher, else 0.

    The last `horizon` rows have no known future and are dropped, so the label
    never peeks past the end of the data.
    """
    out = df.copy()
    future_close = out["Close"].shift(-horizon)
    out["label"] = (future_close > out["Close"]).astype("float")
    return out.dropna(subset=["label"])


def _new_model() -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=200, max_depth=5, random_state=42, class_weight="balanced"
    )


def train_model(
    df: pd.DataFrame,
) -> tuple[RandomForestClassifier, float, pd.DataFrame, pd.DataFrame]:
    """Train on a chronological 80/20 split; return (model, test_accuracy, train_df, test_df).

    The split is chronological (shuffle=False) so test_df is strictly after
    train_df — required for honest out-of-sample backtesting.
    """
    labeled = build_labels(df)
    X = labeled[FEATURE_COLUMNS]
    y = labeled["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    model = _new_model()
    model.fit(X_train, y_train)
    accuracy = model.score(X_test, y_test)

    train_df = labeled.loc[X_train.index]
    test_df = labeled.loc[X_test.index]
    return model, accuracy, train_df, test_df


def walk_forward_predict(
    df: pd.DataFrame, n_splits: int = 5, min_train_frac: float = 0.4
) -> tuple[pd.Series, float]:
    """Expanding-window walk-forward: retrain repeatedly, predict only forward.

    The data after an initial `min_train_frac` warm-up is cut into `n_splits`
    equal test blocks. For each block the model is trained on *everything before
    it* and predicts that block — exactly how a live EOD bot that retrains
    periodically would behave. Returns (proba_up over all tested rows, accuracy).

    This is a more honest performance estimate than a single 80/20 split, which
    only ever tests the one most-recent market regime.
    """
    labeled = build_labels(df)
    X = labeled[FEATURE_COLUMNS]
    y = labeled["label"]
    n = len(labeled)
    if n < 100:
        raise ValueError("not enough rows for walk-forward evaluation")

    start = int(n * min_train_frac)
    bounds = [start + round(i * (n - start) / n_splits) for i in range(n_splits + 1)]

    proba_parts, correct, total = [], 0, 0
    for i in range(n_splits):
        lo, hi = bounds[i], bounds[i + 1]
        if lo == hi:
            continue
        model = _new_model()
        model.fit(X.iloc[:lo], y.iloc[:lo])
        block = X.iloc[lo:hi]
        proba = pd.Series(model.predict_proba(block)[:, 1], index=block.index, name="proba_up")
        proba_parts.append(proba)
        preds = (proba > 0.5).astype("float")
        correct += int((preds.values == y.iloc[lo:hi].values).sum())
        total += len(block)

    all_proba = pd.concat(proba_parts)
    accuracy = correct / total if total else 0.0
    return all_proba, accuracy

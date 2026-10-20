"""Train a model to predict near-term price direction, with walk-forward evaluation."""

from dataclasses import dataclass

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

LEGACY_FEATURES = [
    "return_1d",
    "return_5d",
    "return_10d",
    "return_20d",
    "price_to_sma10",
    "sma10_to_sma50",
    "volatility_20d",
    "rsi_14",
    "volume_z_20",
    "trend_regime_200",
    "market_regime",
]
# Current inputs = legacy set + two volatility/drawdown regime features (harness-tested).
FEATURE_COLUMNS = [*LEGACY_FEATURES, "vol_ratio_20_100", "drawdown_120"]

# Predict direction over this many trading days ahead, not just tomorrow. A
# multi-day horizon has a better signal-to-noise ratio than next-day direction,
# which is almost pure coin-flip.
LABEL_HORIZON = 5


@dataclass(frozen=True)
class ModelSpec:
    """Which algorithm, inputs and prediction target a walk-forward run uses.

    kind: "rf" | "logreg" | "gbm". target: "direction" (does the stock rise?) or
    "excess" (does it beat SPY over the horizon? needs the `spy_close` column).
    """

    kind: str = "logreg"
    features: tuple = tuple(FEATURE_COLUMNS)
    target: str = "direction"


BASELINE_SPEC = ModelSpec("rf", tuple(LEGACY_FEATURES))  # the original model, kept for comparison
DEFAULT_SPEC = ModelSpec()  # what the app/bot use; changed only when the harness says so


def build_labels(df: pd.DataFrame, horizon: int = LABEL_HORIZON, target: str = "direction") -> pd.DataFrame:
    """Label each row 1 if the close `horizon` days later is higher, else 0.

    With target="excess" the label is 1 when the stock's `horizon`-day return
    beats SPY's. The last `horizon` rows have no known future and are dropped,
    so the label never peeks past the end of the data.
    """
    out = df.copy()
    fwd = out["Close"].shift(-horizon) / out["Close"] - 1
    if target == "excess":
        fwd = fwd - (out["spy_close"].shift(-horizon) / out["spy_close"] - 1)
    out["label"] = (fwd > 0).astype("float").where(fwd.notna())
    return out.dropna(subset=["label"])


CALIBRATION_FRAC = 0.2  # newest slice of each training window, used only to calibrate


def _new_model(kind: str = "rf"):
    if kind == "logreg":  # simple, strongly regularized linear model
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.02, max_iter=500))
    if kind == "gbm":  # shallow, slow, heavily regularized boosting
        return HistGradientBoostingClassifier(
            max_depth=2, learning_rate=0.03, max_iter=120, l2_regularization=10.0,
            min_samples_leaf=100, random_state=42)
    return RandomForestClassifier(
        n_estimators=200, max_depth=5, random_state=42, class_weight="balanced", n_jobs=-1
    )


def _fit_model(X: pd.DataFrame, y: pd.Series, kind: str = "rf"):
    """Fit the forest, then calibrate its probabilities on the newest slice.

    The calibration slice comes strictly after the fitting slice (time order is
    kept), so calibration never sees the future of the data it is applied to.
    Falls back to the raw forest when the slice is too small or one-class.
    """
    n_cal = int(len(X) * CALIBRATION_FRAC)
    fit_end = len(X) - n_cal - LABEL_HORIZON  # purge gap before the calibration slice
    y_cal = y.iloc[-n_cal:] if n_cal else y.iloc[:0]
    if n_cal < 30 or fit_end < 50 or y_cal.nunique() < 2 or y.iloc[:fit_end].nunique() < 2:
        model = _new_model(kind)
        model.fit(X, y)
        return model
    forest = _new_model(kind)
    forest.fit(X.iloc[:fit_end], y.iloc[:fit_end])
    calibrated = CalibratedClassifierCV(FrozenEstimator(forest), method="sigmoid")
    calibrated.fit(X.iloc[-n_cal:], y_cal)
    return calibrated


def train_model(
    df: pd.DataFrame, spec: ModelSpec | None = None,
) -> tuple[RandomForestClassifier, float, pd.DataFrame, pd.DataFrame]:
    """Train on a chronological 80/20 split; return (model, test_accuracy, train_df, test_df).

    The split is chronological (shuffle=False) so test_df is strictly after
    train_df — required for honest out-of-sample backtesting.
    """
    spec = spec or DEFAULT_SPEC
    labeled = build_labels(df, target=spec.target)
    X = labeled[list(spec.features)]
    y = labeled["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    # Purge: the last LABEL_HORIZON training labels are computed from prices inside
    # the test window, so they are left out of fitting (no look-ahead).
    model = _fit_model(X_train.iloc[:-LABEL_HORIZON], y_train.iloc[:-LABEL_HORIZON], spec.kind)
    accuracy = model.score(X_test, y_test)

    train_df = labeled.loc[X_train.index]
    test_df = labeled.loc[X_test.index]
    return model, accuracy, train_df, test_df


def walk_forward_predict(
    df: pd.DataFrame, n_splits: int = 5, min_train_frac: float = 0.4, spec: ModelSpec | None = None
) -> tuple[pd.Series, float]:
    """Expanding-window walk-forward: retrain repeatedly, predict only forward.

    The data after an initial `min_train_frac` warm-up is cut into `n_splits`
    equal test blocks. For each block the model is trained on *everything before
    it* and predicts that block — exactly how a live EOD bot that retrains
    periodically would behave. Returns (proba_up over all tested rows, accuracy).

    This is a more honest performance estimate than a single 80/20 split, which
    only ever tests the one most-recent market regime. Training stops
    LABEL_HORIZON rows before each block, because those rows' labels are
    computed from prices inside the block.
    """
    spec = spec or DEFAULT_SPEC
    labeled = build_labels(df, target=spec.target)
    X = labeled[list(spec.features)]
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
        train_end = max(0, lo - LABEL_HORIZON)  # purge labels that peek into the block
        model = _fit_model(X.iloc[:train_end], y.iloc[:train_end], spec.kind)
        block = X.iloc[lo:hi]
        proba = pd.Series(model.predict_proba(block)[:, 1], index=block.index, name="proba_up")
        proba_parts.append(proba)
        preds = (proba > 0.5).astype("float")
        correct += int((preds.values == y.iloc[lo:hi].values).sum())
        total += len(block)

    all_proba = pd.concat(proba_parts)
    accuracy = correct / total if total else 0.0
    return all_proba, accuracy


def latest_signal(df: pd.DataFrame, spec: ModelSpec | None = None) -> tuple[float, pd.Timestamp]:
    """Train on every labeled row, then score the newest row (which has no label yet).

    Returns (P(up over LABEL_HORIZON days), date of the row scored).
    """
    spec = spec or DEFAULT_SPEC
    cols = list(spec.features)
    labeled = build_labels(df, target=spec.target)
    model = _fit_model(labeled[cols], labeled["label"], spec.kind)
    latest = df[cols].iloc[[-1]]
    return float(model.predict_proba(latest)[0, 1]), df.index[-1]


def training_prior(df: pd.DataFrame, first_test_index, spec: ModelSpec | None = None) -> float:
    """Share of 'up' labels among rows whose label was fully known before `first_test_index`.

    This is what a base-rate predictor could honestly have quoted when the first out-of-sample day
    arrived: the stock's up-frequency in its training history (the last LABEL_HORIZON rows are left
    out because their labels peek into the test window).
    """
    spec = spec or DEFAULT_SPEC
    labels = build_labels(df, target=spec.target)["label"]
    pos = int(labels.index.searchsorted(first_test_index))
    known = labels.iloc[: max(0, pos - LABEL_HORIZON)]
    return float(known.mean()) if len(known) else 0.5

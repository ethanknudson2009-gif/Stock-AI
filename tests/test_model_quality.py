"""Tests for purged walk-forward, calibration, diagnostics, baselines and portfolio extras."""

import numpy as np
import pandas as pd

from stock_ai.backtest.multi_engine import run_multi_backtest
from stock_ai.features.indicators import add_features
from stock_ai.models import classifier
from stock_ai.models.evaluation import classification_stats
from stock_ai.strategy.baselines import momentum_weights, sma_crossover_positions


def _prices(n=900, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, n)))
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    vol = rng.integers(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame({"Close": close, "Volume": vol}, index=idx)


def test_walk_forward_purges_labels_that_peek_into_the_test_block(monkeypatch):
    df = add_features(_prices())
    seen = []
    real_fit = classifier._fit_model

    def spy(X, y):
        seen.append(X.index[-1])
        return real_fit(X, y)

    monkeypatch.setattr(classifier, "_fit_model", spy)
    proba, _ = classifier.walk_forward_predict(df, n_splits=4)
    labeled_idx = classifier.build_labels(df).index
    block_starts = [labeled_idx.get_loc(d) for d in proba.index[[0]]]
    # The first model must stop >= LABEL_HORIZON rows before its test block.
    last_train_pos = labeled_idx.get_loc(seen[0])
    assert block_starts[0] - last_train_pos > classifier.LABEL_HORIZON


def test_calibrated_model_outputs_valid_probabilities():
    df = add_features(_prices())
    labeled = classifier.build_labels(df)
    model = classifier._fit_model(labeled[classifier.FEATURE_COLUMNS], labeled["label"])
    p = model.predict_proba(labeled[classifier.FEATURE_COLUMNS].tail(50))[:, 1]
    assert ((p >= 0) & (p <= 1)).all()


def test_latest_signal_scores_the_newest_row():
    df = add_features(_prices())
    p, day = classifier.latest_signal(df)
    assert 0.0 <= p <= 1.0
    assert day == df.index[-1]


def test_new_features_present_and_market_regime_neutral_without_market():
    df = add_features(_prices())
    for col in ("volume_z_20", "trend_regime_200", "market_regime"):
        assert col in df.columns
    assert (df["market_regime"] == 1.0).all()


def test_classification_stats_confusion_matrix():
    idx = pd.date_range("2024-01-01", periods=6, freq="B")
    proba = pd.Series([0.9, 0.8, 0.2, 0.1, 0.7, 0.3], index=idx)
    labels = pd.Series([1, 0, 1, 0, 1, 0], index=idx)
    s = classification_stats(proba, labels, threshold=0.5)
    assert s["confusion"] == {"tp": 2, "fp": 1, "fn": 1, "tn": 2}
    assert abs(s["precision"] - 2 / 3) < 1e-9
    assert abs(s["recall"] - 2 / 3) < 1e-9
    assert abs(s["base_rate"] - 0.5) < 1e-9


def test_sma_crossover_uses_only_past_prices():
    df = _prices(400)
    full = sma_crossover_positions(df)
    truncated = sma_crossover_positions(df.iloc[:300])
    pd.testing.assert_series_equal(full.iloc[:300], truncated)  # future rows don't change the past


def test_momentum_picks_strongest_trailing_return():
    idx = pd.date_range("2024-01-01", periods=10, freq="B")
    rets = pd.DataFrame({"A": [0.02] * 10, "B": [0.0] * 10, "C": [-0.01] * 10}, index=idx)
    w = momentum_weights(rets, n=1, lookback=5)
    assert w.iloc[-1]["A"] == 1.0 and w.iloc[-1]["B"] == 0.0


def test_portfolio_contributions_and_benchmark_skip_missing():
    idx = pd.date_range("2024-01-01", periods=4, freq="B")
    rets = pd.DataFrame({"A": [0.01, 0.01, 0.01, 0.01], "B": [np.nan, np.nan, 0.03, 0.03]}, index=idx)
    w = pd.DataFrame({"A": [1.0] * 4, "B": [0.0] * 4}, index=idx)
    r = run_multi_backtest(rets, w, cost_bps=0)
    # Contributions add up to the gross portfolio return path.
    assert abs(r["contributions"].sum() - r["portfolio_returns"].sum()) < 1e-12
    # Benchmark day 1 is A's 1% alone, not (1% + 0%) / 2.
    assert abs(r["benchmark_cumulative"].iloc[0] - 1.01) < 1e-12
    assert r["turnover_daily"] >= 0

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

    def spy(X, y, *a, **k):
        seen.append(X.index[-1])
        return real_fit(X, y, *a, **k)

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


def test_edge_check_flags_a_model_no_better_than_the_base_rate():
    from stock_ai.models.evaluation import edge_check

    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    rng = np.random.default_rng(1)
    labels = pd.Series((rng.random(400) < 0.58).astype(float), index=idx)
    noise = pd.Series(rng.uniform(0.2, 0.8, 400), index=idx)           # confident but uninformed
    informed = (labels * 0.7 + (1 - labels) * 0.3).rename("p")         # genuinely predictive
    assert not edge_check(noise, labels)["has_edge"]
    assert edge_check(informed, labels)["has_edge"]


def test_block_bootstrap_ci_brackets_the_point_estimate():
    from stock_ai.backtest.engine import _sharpe_ratio
    from stock_ai.models.evaluation import block_bootstrap_sharpe

    r = pd.Series(np.random.default_rng(2).normal(0.0006, 0.01, 1500))
    lo, hi = block_bootstrap_sharpe(r)
    assert lo < _sharpe_ratio(r) < hi
    assert hi - lo > 0.3  # a Sharpe from a few years of data is genuinely uncertain
    assert all(np.isnan(block_bootstrap_sharpe(r.iloc[:10])))


def test_vol_target_shrinks_positions_when_volatility_is_high():
    from stock_ai.strategy.sizing import vol_target_positions

    idx = pd.date_range("2024-01-01", periods=3, freq="B")
    pos = vol_target_positions(pd.Series([1.0, 1.0, 0.0], index=idx), pd.Series([0.005, 0.04, 0.04], index=idx))
    assert pos.iloc[0] == 1.0 and 0 < pos.iloc[1] < 0.5 and pos.iloc[2] == 0.0


def test_excess_labels_compare_against_spy():
    df = pd.DataFrame({"Close": [100.0, 110, 121, 133, 146, 160, 176, 193],
                       "spy_close": [100.0, 120, 140, 160, 180, 200, 230, 260]},
                      index=pd.date_range("2024-01-01", periods=8, freq="B"))
    assert classifier.build_labels(df, horizon=2, target="excess")["label"].eq(0).all()   # SPY outran it
    assert classifier.build_labels(df, horizon=2)["label"].eq(1).all()                    # but it still rose
    assert len(classifier.build_labels(df, horizon=2)) == 6                                 # tail dropped


def test_news_sentiment_scores_and_negation():
    from stock_ai.data.news import score_text

    assert score_text("Apple beats estimates, raises guidance, stock surges") > 0.5
    assert score_text("Company misses, cuts outlook amid probe") < -0.5
    assert score_text("Results not strong") < 0          # negator flips 'strong'
    assert score_text("Company holds annual meeting") == 0.0


def test_news_ranking_weights_recency_roundups_and_thin_coverage():
    from stock_ai.data.news import rank_tickers

    now = pd.Timestamp("2026-10-16 18:00", tz="UTC")
    news = pd.DataFrame([
        {"time": now - pd.Timedelta(hours=1), "symbols": ["AAA"], "sentiment": 0.8},
        {"time": now - pd.Timedelta(hours=2), "symbols": ["AAA"], "sentiment": 0.6},
        {"time": now - pd.Timedelta(hours=1), "symbols": ["BBB"], "sentiment": 1.0},                 # one article only
        {"time": now - pd.Timedelta(hours=3), "symbols": ["CCC", "AAA", "BBB", "DDD", "EEE"], "sentiment": -1.0},
    ])
    r = rank_tickers(news, ["AAA", "BBB", "CCC"], now=now).set_index("ticker")
    assert r.loc["AAA", "articles"] == 3 and r.loc["AAA", "score"] > 0.3
    assert r.loc["BBB", "score"] < r.loc["BBB", "sentiment"]       # thin coverage is shrunk
    assert r.loc["AAA", "score"] > r.loc["BBB", "score"]
    assert r.loc["CCC", "score"] < 0


def test_news_lexicon_catches_lowered_price_targets():
    from stock_ai.data.news import score_text

    assert score_text("Analyst maintains outperform but lowers price target") == 0.0   # mixed, not +1


def test_claude_scoring_parses_caches_and_falls_back(tmp_path, monkeypatch):
    from types import SimpleNamespace as NS

    from stock_ai.data import sentiment

    monkeypatch.setattr(sentiment, "CACHE", tmp_path / "cache.json")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    calls = []

    class FakeClient:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                calls.append(1)
                return NS(content=[NS(text='noise {"1": 0.6, "2": -2.0} noise')], usage=NS(input_tokens=10, output_tokens=5))

    news = pd.DataFrame({"id": ["a", "b"], "headline": ["Up", "Down"], "summary": ["", ""], "symbols": [["X"], ["Y"]]})
    s, st = sentiment.score_with_claude(news, client=FakeClient())
    assert list(s) == [0.6, -1.0] and st["new"] == 2                   # out-of-range score is clamped
    s2, st2 = sentiment.score_with_claude(news, client=FakeClient())   # second time: cache, no new API call
    assert len(calls) == 1 and st2["cached"] == 2 and list(s2) == [0.6, -1.0]
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    s3, _ = sentiment.score_with_claude(news.assign(id=["c", "d"]))    # no key: NaN -> caller falls back to word list
    assert s3.isna().all()

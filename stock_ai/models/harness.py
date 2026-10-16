"""Model-vs-baseline harness: the same purged walk-forward across many tickers.

A change to the model is kept only if it wins here — median Sharpe, median excess
return over buy & hold, and Brier score vs. the base-rate predictor — not on one
ticker. Every number is out-of-sample.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from stock_ai.backtest.engine import run_backtest
from stock_ai.features.indicators import add_features
from stock_ai.models.classifier import LABEL_HORIZON, ModelSpec, build_labels, walk_forward_predict
from stock_ai.models.evaluation import base_rate_brier
from stock_ai.strategy.baselines import buy_hold_positions
from stock_ai.strategy.sizing import vol_target_positions


def build_frames(raw: dict[str, pd.DataFrame], start: str = "2010-01-01") -> dict[str, pd.DataFrame]:
    """Featured frames per ticker from raw OHLCV; `raw` must include 'SPY'."""
    spy = raw["SPY"]["Close"]
    out = {}
    for t, df in raw.items():
        if t == "SPY":
            continue
        feats = add_features(df, market_close=spy)
        out[t] = feats.loc[feats.index >= pd.Timestamp(start)]
    return out


@dataclass
class Variant:
    name: str
    spec: ModelSpec = field(default_factory=ModelSpec)
    sizing: str = "binary"        # "binary" | "voltarget"
    threshold: float = 0.5
    extra: dict = field(default_factory=dict)


def _cagr(cum: pd.Series) -> float:
    years = max((cum.index[-1] - cum.index[0]).days / 365.25, 1e-9)
    return float(cum.iloc[-1] ** (1 / years) - 1)


def evaluate_ticker(df: pd.DataFrame, v: Variant, cost_bps: float = 10.0) -> dict:
    proba, _ = walk_forward_predict(df, spec=v.spec)
    wf = df.loc[proba.index]
    if v.spec.target == "excess":
        # P(beats SPY): go long when it clears the threshold (market-beating odds).
        pass
    signal = (proba > v.threshold).astype(float)
    pos = vol_target_positions(signal, wf["volatility_20d"]) if v.sizing == "voltarget" else signal
    m = run_backtest(wf, pos, cost_bps=cost_bps)
    bh = run_backtest(wf, buy_hold_positions(wf), cost_bps=cost_bps)
    labels = build_labels(df, target=v.spec.target)["label"].reindex(proba.index)
    brier = float(((proba - labels) ** 2).mean())
    return {
        "sharpe": m["sharpe_ratio"], "bh_sharpe": bh["sharpe_ratio"],
        "excess_cagr": _cagr(m["cumulative_returns"]) - _cagr(bh["cumulative_returns"]),
        "brier": brier, "base_brier": base_rate_brier(labels),
        "acc": float(((proba > 0.5).astype(float) == labels).mean()),
        "base_rate": float(labels.mean()),
    }


def evaluate(frames: dict[str, pd.DataFrame], v: Variant, cost_bps: float = 10.0) -> dict:
    """Run one variant over every ticker; return per-ticker rows and the medians."""
    rows = {}
    for t, df in frames.items():
        try:
            rows[t] = evaluate_ticker(df, v, cost_bps)
        except (ValueError, IndexError, KeyError):
            continue
    tab = pd.DataFrame(rows).T
    return {
        "name": v.name, "n": len(tab), "table": tab,
        "median_sharpe": float(tab["sharpe"].median()),
        "median_bh_sharpe": float(tab["bh_sharpe"].median()),
        "median_excess_cagr": float(tab["excess_cagr"].median()),
        "median_brier": float(tab["brier"].median()),
        "median_base_brier": float(tab["base_brier"].median()),
        "brier_beats_base": int((tab["brier"] < tab["base_brier"]).sum()),
        "median_acc": float(tab["acc"].median()),
        "median_base_rate": float(tab["base_rate"].median()),
    }


def summary_line(r: dict) -> str:
    return (f"{r['name']:<28} n={r['n']:>2} | Sharpe {r['median_sharpe']:+.2f} (B&H {r['median_bh_sharpe']:.2f}) | "
            f"excess CAGR {r['median_excess_cagr']:+.1%} | Brier {r['median_brier']:.4f} vs base "
            f"{r['median_base_brier']:.4f} ({r['brier_beats_base']}/{r['n']} beat) | "
            f"acc {r['median_acc']:.1%} vs {r['median_base_rate']:.1%}")

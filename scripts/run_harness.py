"""Run model variants through the 30-ticker harness: python scripts/run_harness.py [name ...]"""

import sys
import time
from pathlib import Path

import pandas as pd

from stock_ai.features.indicators import RANK_COLUMNS, add_cross_sectional_ranks
from stock_ai.models.classifier import LEGACY_FEATURES, ModelSpec
from stock_ai.models.harness import Variant, build_frames, evaluate, summary_line

CACHE = Path("data/cache/raw.pkl")
BASE = tuple(LEGACY_FEATURES)
VARIANTS = {
    "baseline_rf": Variant("baseline_rf", ModelSpec("rf", BASE)),
    "current": Variant("current", ModelSpec()),
    "logreg": Variant("logreg", ModelSpec("logreg", BASE)),
    "gbm": Variant("gbm", ModelSpec("gbm", BASE)),
}
SMALL = ("return_20d", "volatility_20d", "vol_ratio_20_100", "rsi_14", "trend_regime_200", "market_regime")
TINY = ("return_20d", "vol_ratio_20_100", "trend_regime_200", "market_regime")
WIDE = (*BASE, "vol_ratio_20_100", "drawdown_120")
for kind in ("logreg", "gbm"):
    VARIANTS[f"{kind}_small"] = Variant(f"{kind}_small", ModelSpec(kind, SMALL))
    VARIANTS[f"{kind}_tiny"] = Variant(f"{kind}_tiny", ModelSpec(kind, TINY))
    VARIANTS[f"{kind}_wide"] = Variant(f"{kind}_wide", ModelSpec(kind, WIDE))
    VARIANTS[f"{kind}_small_excess"] = Variant(f"{kind}_small_excess", ModelSpec(kind, SMALL, "excess"))
    VARIANTS[f"{kind}_small_vt"] = Variant(f"{kind}_small_vt", ModelSpec(kind, SMALL), sizing="voltarget")
    VARIANTS[f"{kind}_small_excess_vt"] = Variant(f"{kind}_small_excess_vt", ModelSpec(kind, SMALL, "excess"), sizing="voltarget")
for kind in ("logreg", "gbm", "rf"):
    VARIANTS[f"{kind}_ranks"] = Variant(f"{kind}_ranks", ModelSpec(kind, (*WIDE, *RANK_COLUMNS)))
VARIANTS["rf_vt"] = Variant("rf_vt", ModelSpec("rf", BASE), sizing="voltarget")

def ensure_cache() -> None:
    """Download 2009-now prices for the 30-stock universe + SPY the first time (not committed to git)."""
    if CACHE.exists():
        return
    from stock_ai.config import DEFAULT_UNIVERSE
    from stock_ai.data.loader import fetch_price_history

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle({t: fetch_price_history(t, "2009-01-01") for t in [*DEFAULT_UNIVERSE, "SPY"]}, CACHE)


if __name__ == "__main__":
    ensure_cache()
    frames = add_cross_sectional_ranks(build_frames(pd.read_pickle(CACHE)))
    names = sys.argv[1:] or list(VARIANTS)
    for n in names:
        t0 = time.time()
        r = evaluate(frames, VARIANTS[n])
        print(summary_line(r), f"[{time.time() - t0:.0f}s]", flush=True)

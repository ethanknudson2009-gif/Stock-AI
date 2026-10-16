"""Log every model signal and, once enough days pass, whether the stock actually rose.

Lets live accuracy be tracked against the backtest. Pure file I/O on a CSV path; no network.
"""

from pathlib import Path

import pandas as pd

from stock_ai.models.classifier import LABEL_HORIZON

COLUMNS = ["date", "ticker", "p_up", "price", "outcome_date", "outcome_price", "went_up"]


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path, dtype={"date": str, "ticker": str, "outcome_date": str})


def log_signals(proba: dict[str, float], prices: dict[str, float], day, path: Path) -> int:
    """Append today's signals, once per (date, ticker). Returns how many rows were added."""
    log = _read(path)
    seen = set(zip(log["date"], log["ticker"]))
    rows = [{"date": str(day), "ticker": t, "p_up": round(p, 4), "price": prices.get(t)}
            for t, p in proba.items() if (str(day), t) not in seen]
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([log, pd.DataFrame(rows, columns=COLUMNS)], ignore_index=True).to_csv(path, index=False)
    return len(rows)


def resolve_outcomes(closes: dict[str, pd.Series], path: Path, horizon: int = LABEL_HORIZON) -> pd.DataFrame:
    """Fill outcome columns for signals whose `horizon`-th later trading day now exists in `closes`."""
    log = _read(path)
    if log.empty:
        return log
    for i, row in log.iterrows():
        if pd.notna(row["went_up"]) or row["ticker"] not in closes:
            continue
        s = closes[row["ticker"]]
        later = s[s.index > pd.Timestamp(row["date"])]
        if len(later) < horizon or pd.isna(row["price"]):
            continue
        log.loc[i, ["outcome_date", "outcome_price"]] = [str(later.index[horizon - 1].date()), float(later.iloc[horizon - 1])]
        log.loc[i, "went_up"] = float(later.iloc[horizon - 1] > row["price"])
    log.to_csv(path, index=False)
    return log


def live_accuracy(log: pd.DataFrame, threshold: float = 0.5) -> dict:
    """Live hit-rate of resolved signals vs. the share that went up (the base rate)."""
    done = log.dropna(subset=["went_up"])
    if done.empty:
        return {"n": 0, "accuracy": None, "base_rate": None, "pending": len(log)}
    hit = ((done["p_up"] > threshold).astype(float) == done["went_up"].astype(float)).mean()
    return {"n": len(done), "accuracy": float(hit), "base_rate": float(done["went_up"].astype(float).mean()),
            "pending": len(log) - len(done)}

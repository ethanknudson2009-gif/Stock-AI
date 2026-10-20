"""One ticker, scored the same way the app judges it: today's P(up) plus the reliable-edge verdict.

The paper bot used to train a different model (80% of a shorter history, no market-regime input) than
the one the app's edge check evaluated. This module is the single recipe both can share:
featured history -> walk-forward out-of-sample record -> edge check -> a model fit on every labeled row.
"""

from datetime import date, datetime, time, timedelta

import pandas as pd

from stock_ai.data.loader import fetch_price_history
from stock_ai.execution.clock import now_eastern
from stock_ai.features.indicators import add_features
from stock_ai.models.classifier import build_labels, latest_signal, training_prior, walk_forward_predict
from stock_ai.models.evaluation import edge_check

HISTORY_START = date(2010, 1, 1)   # same "Max" window the app uses for its edge verdicts
WARMUP_DAYS = 420                  # extra history so 200-day features exist from HISTORY_START
FINAL_BAR_AFTER = time(16, 15)     # a daily bar is final shortly after the 4 PM ET close


def drop_unfinished_bar(df: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    """Remove today's bar while the market is still open — a half-finished day is not a close."""
    now = now or now_eastern()
    if len(df) and df.index[-1].date() >= now.date() and (now.weekday() >= 5 or now.time() < FINAL_BAR_AFTER):
        return df.iloc[:-1]
    return df


def featured_history(ticker: str, start: date = HISTORY_START, end: date | None = None,
                     now: datetime | None = None) -> pd.DataFrame:
    """Daily features from `start`, with SPY as the market-regime input, never ending on an unfinished bar."""
    warm = (start - timedelta(days=WARMUP_DAYS)).isoformat()
    stop = None if end is None else (end + timedelta(days=1)).isoformat()
    prices = drop_unfinished_bar(fetch_price_history(ticker, warm, stop), now)
    try:
        spy = drop_unfinished_bar(fetch_price_history("SPY", warm, stop), now)["Close"]
    except Exception:  # noqa: BLE001 — without SPY the regime feature is a neutral constant
        spy = None
    feats = add_features(prices, market_close=spy)
    return feats.loc[feats.index >= pd.Timestamp(start)]


def evaluate_ticker(ticker: str, now: datetime | None = None) -> dict:
    """{'p_up', 'has_edge', 'as_of', 'margin_lo'} for one ticker; raises if data is missing or too short."""
    df = featured_history(ticker, now=now)
    if len(df) < 120:
        raise ValueError(f"{ticker}: not enough history")
    proba, _acc = walk_forward_predict(df)
    labels = build_labels(df)["label"].reindex(proba.index)
    edge = edge_check(proba, labels, prior=training_prior(df, proba.index[0]))
    p_up, as_of = latest_signal(df)
    return {"p_up": p_up, "has_edge": edge["has_edge"], "as_of": as_of, "margin_lo": edge["margin_lo"]}

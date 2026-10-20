"""Fetch ticker news from Alpaca (Benzinga) and score it for sentiment.

Sentiment here is a transparent finance-word lexicon, not a trained model: it is crude, but
free, instant and explainable. Treat the ranking as a lead generator for research, not a signal
with proven edge — the pick log (see stock_ai/execution/signal_log.py) measures whether it works.
"""

import re
from datetime import datetime, timedelta, timezone

import pandas as pd

from stock_ai.config import load_settings

POSITIVE = {
    "beat", "beats", "surge", "surges", "soar", "soars", "jump", "jumps", "rally", "rallies", "gain", "gains",
    "upgrade", "upgrades", "upgraded", "outperform", "raises", "raised", "record", "strong", "growth", "profit",
    "profits", "bullish", "boost", "boosts", "wins", "win", "approval", "approved", "partnership", "expands",
    "buyback", "dividend", "breakthrough", "tops", "exceeds", "optimistic", "recovery", "rebound", "climbs", "raise",
}
NEGATIVE = {
    "miss", "misses", "missed", "plunge", "plunges", "fall", "falls", "drop", "drops", "slump", "slumps", "decline",
    "declines", "downgrade", "downgrades", "downgraded", "underperform", "cuts", "cut", "weak", "loss", "losses",
    "bearish", "lawsuit", "sues", "probe", "investigation", "recall", "fraud", "layoffs", "warning", "warns",
    "delay", "delays", "halt", "bankruptcy", "default", "slashes", "tumbles", "sinks", "concern", "concerns", "fears", "lowers", "lowered", "lower", "trims", "reduces", "reduced",
}
NEGATORS = {"not", "no", "never", "without", "fails", "failed", "despite"}
_WORD = re.compile(r"[a-z']+")


def score_text(text: str) -> float:
    """Sentiment in [-1, 1]: (positive − negative words) / (positive + negative), 0 if none.

    A negator right before a sentiment word flips it ('not strong' counts as negative).
    """
    words = _WORD.findall((text or "").lower())
    pos = neg = 0
    for i, w in enumerate(words):
        sign = 1 if w in POSITIVE else -1 if w in NEGATIVE else 0
        if sign and i > 0 and words[i - 1] in NEGATORS:
            sign = -sign
        pos += sign > 0
        neg += sign < 0
    return (pos - neg) / (pos + neg) if pos + neg else 0.0


def fetch_news(symbols: list[str], days: int = 3, limit: int = 600, now: datetime | None = None,
               use_llm: bool = False) -> pd.DataFrame:
    """Recent Alpaca news for `symbols`: id, time, headline, summary, source, url, symbols, sentiment.

    `sentiment` is the word-list score; with use_llm=True it is replaced by Claude's score wherever one
    exists (cached), keeping the word-list value in `sentiment_lex` and Claude's in `sentiment_llm`.
    """
    from alpaca.data.historical.news import NewsClient  # noqa: PLC0415
    from alpaca.data.requests import NewsRequest  # noqa: PLC0415

    settings = load_settings()
    if not (settings.alpaca_api_key and settings.alpaca_secret_key):
        raise ValueError("Alpaca keys are needed for news — add ALPACA_API_KEY and ALPACA_SECRET_KEY to .env")
    client = NewsClient(settings.alpaca_api_key, settings.alpaca_secret_key)
    start = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    # alpaca-py pages internally until `limit` articles (50 per request) or the window is exhausted.
    resp = client.get_news(NewsRequest(symbols=",".join(symbols), start=start, limit=limit, sort="desc",
                                       include_content=False))
    rows = [{"id": str(a.id), "time": pd.Timestamp(a.created_at), "headline": a.headline, "summary": a.summary or "",
             "source": a.source, "url": a.url, "symbols": list(a.symbols),
             "sentiment": score_text(f"{a.headline}. {a.summary or ''}")} for a in resp.data.get("news", [])]
    df = pd.DataFrame(rows, columns=["id", "time", "headline", "summary", "source", "url", "symbols", "sentiment"])
    df = df.drop_duplicates("id").drop_duplicates(["headline", "source"]).reset_index(drop=True)   # re-posted wire copy
    df["sentiment_lex"] = df["sentiment"]
    df["sentiment_llm"] = float("nan")
    if use_llm and len(df):
        from stock_ai.data.sentiment import score_with_claude  # noqa: PLC0415

        df["sentiment_llm"], df.attrs["llm_stats"] = score_with_claude(df)
        df["sentiment"] = df["sentiment_llm"].fillna(df["sentiment_lex"])
    return df


def rank_tickers(news: pd.DataFrame, universe: list[str], now: pd.Timestamp | None = None,
                 half_life_hours: float = 24.0, thin_below: float = 2.0) -> pd.DataFrame:
    """Per-ticker news score: recency-weighted average sentiment, shrunk when coverage is thin.

    Each article counts for 1/(number of tickers it tags), so a 10-stock roundup doesn't swamp a
    story about one company, and fades with a `half_life_hours` half-life. `weight` is the
    effective article count; below `thin_below` the score is scaled down in proportion.
    """
    now = now or pd.Timestamp.now(tz="UTC")
    acc = {t: {"sw": 0.0, "w": 0.0, "n": 0} for t in universe}
    for _, a in news.iterrows():
        age_h = max((now - a["time"]).total_seconds() / 3600, 0.0)
        decay = 0.5 ** (age_h / half_life_hours)
        tagged = [s for s in a["symbols"] if s in acc]
        for s in tagged:
            w = decay / max(len(a["symbols"]), 1)
            acc[s]["sw"] += w * a["sentiment"]
            acc[s]["w"] += w
            acc[s]["n"] += 1
    rows = []
    for t, v in acc.items():
        avg = v["sw"] / v["w"] if v["w"] else 0.0
        conf = min(1.0, v["w"] / thin_below)
        rows.append({"ticker": t, "articles": v["n"], "weight": v["w"], "sentiment": avg, "score": avg * conf})
    out = pd.DataFrame(rows).sort_values("score", ascending=False, ignore_index=True)
    out["label"] = out.apply(lambda r: "Thin coverage" if r["weight"] < thin_below / 2 else
                             "Bullish" if r["score"] > 0.15 else "Bearish" if r["score"] < -0.15 else "Mixed", axis=1)
    return out


def top_headlines(news: pd.DataFrame, ticker: str, n: int = 8) -> pd.DataFrame:
    """Newest `n` articles that tag `ticker`."""
    mask = news["symbols"].apply(lambda s: ticker in s)
    return news[mask].sort_values("time", ascending=False).head(n)



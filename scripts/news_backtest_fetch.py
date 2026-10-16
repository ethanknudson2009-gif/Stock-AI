"""Download ~2 years of Alpaca news per ticker into data/cache/news_hist.pkl (for scripts/news_backtest.py)."""

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from stock_ai.config import DEFAULT_UNIVERSE, load_settings  # noqa: E402

OUT = ROOT / "data" / "cache" / "news_hist.pkl"


def main(years: float = 2.0) -> None:
    from alpaca.data.historical.news import NewsClient
    from alpaca.data.requests import NewsRequest

    s = load_settings()
    client = NewsClient(s.alpaca_api_key, s.alpaca_secret_key)
    start = datetime.now(timezone.utc) - timedelta(days=365 * years)
    rows = {}
    for t in DEFAULT_UNIVERSE:
        t0 = time.time()
        resp = client.get_news(NewsRequest(symbols=t, start=start, limit=10000, sort="asc", include_content=False))
        for a in resp.data.get("news", []):
            rows[a.id] = {"id": a.id, "time": pd.Timestamp(a.created_at), "headline": a.headline,
                          "summary": a.summary or "", "symbols": list(a.symbols)}
        print(f"{t}: running total {len(rows)} articles ({time.time() - t0:.0f}s)", flush=True)
        pd.to_pickle(pd.DataFrame(rows.values()), OUT)


if __name__ == "__main__":
    main()

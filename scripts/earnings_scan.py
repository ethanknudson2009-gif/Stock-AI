"""Mass earnings scan (log-only, no orders): who reports in the next N days, and what does Jev expect?

  python scripts/earnings_scan.py                 # Top 100, next 7 days, show the top 10
  python scripts/earnings_scan.py --days 3 --top 5
Results are appended to logs/earnings_picks.csv so they can be graded against what the stocks actually did.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from stock_ai.config import PRESETS
    from stock_ai.data.news import fetch_news
    from stock_ai.earnings.scan import scan

    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    def headlines(t):
        try:
            return fetch_news([t], days=5, limit=10)["headline"].tolist()
        except Exception:  # noqa: BLE001 -- no news is fine, Jev just gets less to go on
            return []

    rows = scan(PRESETS["Top 100"], days=args.days, top=args.top, headlines_for=headlines)
    if not rows:
        print(f"No Top-100 stocks report in the next {args.days} days (or Yahoo returned nothing).")
        return 0
    print(f"{'ticker':<7}{'reports':<12}{'P(up)':>7}{'P(down)':>9}{'beat':>7}{'conf':>7}{'score':>8}")
    for r in rows:
        print(f"{r['ticker']:<7}{r['report_date']:<12}{r['p_up']:>7.0%}{r['p_down']:>9.0%}{r['beat']:>7.0%}"
              f"{r['confidence']:>7.0%}{r['score']:>+8.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

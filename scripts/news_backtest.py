"""Does news tone predict returns? Backtest of the word-list news score on ~2 years of Alpaca news.

No look-ahead: an article counts from the close of its publish day (next trading day if published after 4pm ET).
Signal at day d's close -> earns day d+1's return. Compare top-N-by-news vs the equal-weight universe.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from stock_ai.backtest.multi_engine import run_multi_backtest  # noqa: E402
from stock_ai.data.news import score_text  # noqa: E402
from stock_ai.models.evaluation import block_bootstrap_sharpe  # noqa: E402
from stock_ai.strategy.ranker import top_n  # noqa: E402

TOP_N, LOOKBACK, THIN = 5, 3, 2.0


def build_scores(news: pd.DataFrame, trading_days: pd.DatetimeIndex, tickers: list[str], col: str = "sentiment") -> pd.DataFrame:
    """Date x ticker news score using only articles published by each day's close."""
    et = news["time"].dt.tz_convert("America/New_York")
    eff = (et + pd.to_timedelta((et.dt.hour >= 16).astype(int), unit="D")).dt.tz_localize(None).dt.normalize()
    pos = trading_days.searchsorted(eff.values, side="left")        # first trading day >= effective date
    news = news.assign(day=np.where(pos < len(trading_days), pos, -1))
    news = news[news["day"] >= 0]
    sw = np.zeros((len(trading_days), len(tickers)))
    w = np.zeros_like(sw)
    idx = {t: i for i, t in enumerate(tickers)}
    for r in news.itertuples():
        weight = 1.0 / max(len(r.symbols), 1)
        for s in r.symbols:
            if s in idx:
                sw[r.day, idx[s]] += weight * getattr(r, col)
                w[r.day, idx[s]] += weight
    csw, cw = pd.DataFrame(sw).rolling(LOOKBACK, min_periods=1).sum().values, pd.DataFrame(w).rolling(LOOKBACK, min_periods=1).sum().values
    avg = np.divide(csw, cw, out=np.zeros_like(csw), where=cw > 0)
    out = pd.DataFrame(avg * np.minimum(1.0, cw / THIN), index=trading_days, columns=tickers)
    return out.where(pd.DataFrame(cw > 0, index=trading_days, columns=tickers))


def main() -> None:
    news = pd.read_pickle(ROOT / "data/cache/news_hist.pkl")
    news["sentiment"] = [score_text(f"{h}. {s}") for h, s in zip(news["headline"], news["summary"])]
    raw = pd.read_pickle(ROOT / "data/cache/raw.pkl")
    tickers = [t for t in raw if t != "SPY"]
    close = pd.DataFrame({t: raw[t]["Close"] for t in tickers})
    news = news[news["time"] >= "2024-01-01"]          # a handful of stray pre-2024 rows would stretch the window
    start = news["time"].min().tz_convert(None).normalize() + pd.Timedelta(days=30)
    close = close.loc[close.index >= start]
    ret = close.pct_change()
    scores = build_scores(news, close.index, tickers)
    print(f"{len(news):,} articles, {close.index[0].date()} -> {close.index[-1].date()}, {len(tickers)} tickers")

    # ---- Information coefficient vs next-5-day return ----
    fwd5 = close.shift(-5) / close - 1
    ic = pd.Series({d: scores.loc[d].corr(fwd5.loc[d], method="spearman") for d in scores.index if scores.loc[d].notna().sum() >= 10}).dropna()
    lo, hi = block_bootstrap_sharpe(ic - 0 + 1e-12, block=10)   # reuse bootstrap: 'Sharpe' of the IC series
    print(f"IC (5d, Spearman): mean {ic.mean():+.4f}, t~{ic.mean() / ic.std() * len(ic) ** 0.5 / 3:+.2f} (overlap-adjusted), "
          f"hit-rate {(ic > 0).mean():.1%}, n={len(ic)} days")

    # ---- Quintile spread ----
    q = scores.rank(axis=1, pct=True)
    top = fwd5.where(q >= 0.8).mean(axis=1).dropna(); bot = fwd5.where(q <= 0.2).mean(axis=1).dropna()
    mkt = fwd5.mean(axis=1)
    print(f"5d fwd return: top quintile {top.mean():+.3%}, bottom {bot.mean():+.3%}, universe {mkt.mean():+.3%}")

    # ---- Portfolio: top-N by news, daily rebalance ----
    for bps in (0, 10):
        covered = scores.notna().sum(axis=1) >= 10     # only trade days where most names have news
        w = top_n(scores, TOP_N).where(covered, 0.0)
        r2 = ret.loc[covered]
        res = run_multi_backtest(r2.fillna(0), w.loc[covered], cost_bps=bps)
        ex = res["portfolio_returns"] - r2.mean(axis=1).fillna(0)
        elo, ehi = block_bootstrap_sharpe(ex, block=20)
        print(f"top-{TOP_N} by news @ {bps} bps: return {res['total_return']:+.1%} vs equal-weight {res['buy_hold_return']:+.1%}, "
              f"Sharpe {res['portfolio_sharpe']:.2f} vs {res['benchmark_sharpe']:.2f}, turnover {res['turnover_daily']:.0%}/day; "
              f"excess-return Sharpe 95% CI [{elo:+.2f}, {ehi:+.2f}]")


if __name__ == "__main__":
    main()

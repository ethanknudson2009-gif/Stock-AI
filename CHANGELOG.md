# Changelog

## 2026-10-16 (later) — Alpaca connected + News Radar
- Alpaca paper keys in `.env`; Paper Trade page now shows the real paper account (verified: $100k cash, no positions). DRY_RUN still on.
- New **News Radar** page: Alpaca/Benzinga headlines for a universe, scored with a transparent finance-word lexicon
  (negation-aware), weighted by freshness and by how many tickers an article tags, shrunk when coverage is thin.
  Shows most positive/negative names, a ranking with price move, per-ticker headlines, and a **track record**:
  each day's top-5 positive-news picks are logged and graded 5 trading days later against the base rate.
- The lexicon is crude (headline words only) and unproven; the track record is how we find out. Not a trade signal.
- **My Trades** page: the Alpaca paper account mirrored in-app (account value, cash, today's change, positions with P&L,
  every order with status/fill price, Bot vs Manual source, and the model's P(up) behind each bot order, plus equity history).
  Read-only; orders are still placed through Paper Trade. First live paper batch: 5 x $500 buys (AVGO, JPM, META, NVDA, PEP).
- Stress tests (30 tickers): Sharpe vs buy & hold 0.68/0.66/0.64/0.56 at 0/5/10/25 bps; worse in every sub-period
  (2010-17, 2017-22, 2022-26); higher thresholds hurt; shuffled-label control scored the same Sharpe (0.64) — the model
  mostly tracks buy & hold, with at best a tiny edge (Brier beat base rate on 12/30 real vs 8/30 shuffled).
- **Daily job** (`scripts/daily_job.py`, installed as launch agent `com.stockai.daily` via `scripts/install_daily_job.py`):
  weekdays after the close it logs the model's signals, rebalances the Alpaca PAPER account to the top-5 (caps + KILL_SWITCH
  apply), logs news picks, and grades old signals/picks. Skips weekends/holidays and runs once per day. Output: `logs/daily_job.log`.
  Disable: `python scripts/install_daily_job.py --uninstall`, or `touch KILL_SWITCH` to halt orders only.
- Home page links to it; guard test now allows `stock_ai/data/news.py` to use the read-only `alpaca.data` client
  (still forbidden from `alpaca.trading`).

## 2026-10-16 — Honest model + honest UI

### Headline
**The model still has no reliable edge.** Across 30 large-cap tickers (2010–2026, same purged walk-forward, 10 bps costs):

| Metric (median of 30 tickers) | Before (RF, 11 features) | After (logistic reg., 13 features) | Buy & hold / base rate |
|---|---|---|---|
| Sharpe | 0.60 | 0.64 | 0.65 |
| Excess CAGR vs buy & hold | −2.0% | −1.5% | — |
| Brier (lower = better) | 0.2493 | 0.2505 | 0.2491 (base-rate predictor) |
| Tickers where Brier beats the base rate | 13 / 30 | 12 / 30 | — |
| Accuracy | 54.7% | 55.1% | 55.9% (always "up") |
| Time to run all 30 tickers | ~70 s | ~2 s | — |

Neither version beats buy & hold or the base rate. The switch to logistic regression is **not** an edge improvement:
it is equal-or-slightly-better on Sharpe/excess return, slightly worse on Brier (noise-level), and ~35x faster,
which is what makes sub-3-second reruns possible. The app now says so (see "No edge").

### Model (`stock_ai/models`, `scripts/run_harness.py`)
- New 30-ticker harness (`stock_ai/models/harness.py`): median Sharpe, median excess CAGR vs buy & hold, Brier vs base-rate Brier.
- `ModelSpec` (algorithm / features / target) so variants are swappable; walk-forward and purge-gap methodology untouched.
- **Bug fix:** `build_labels` never dropped the last 5 rows (NaN comparison gave "down" labels). Now dropped, as documented.
- New features: `vol_ratio_20_100` (volatility regime), `drawdown_120`.
- Minimum-edge rule (`edge_check`): if OOS Brier is not below the base-rate predictor's, no Buy/Sell is issued.
- Moving-block bootstrap 95% CI for Sharpe; vol-target sizing (`strategy/sizing.py`); cross-sectional rank features; excess-vs-SPY target (all tested, see below).

### UI
- Today's signal: **Buy / Sell / "No edge"**, raw P(up) plus base-rate-adjusted confidence (P(up) minus historical up-frequency).
- Verdict banner: beat buy & hold? beat SMA crossover? better calibrated than chance?
- Results table shows Sharpe with 95% bootstrap CI; "Net of costs" chart at 0/5/10/25 bps.
- "Results from" defaults to the first out-of-sample date, shown explicitly with the training range.
- Compare mode (up to 4 tickers); ticker autocomplete (type-ahead, any symbol allowed) and friendly bad-symbol errors.
- Skeleton loader on Single Ticker; logo `src` fixed per session and light theme painted via CSS (no swap on load).
- Portfolio: SPY added beside equal-weight and momentum (table, chart, stats, CSV).
- Paper Trade: open positions + unrealized P&L (Alpaca), per-ticker "Model edge?" column with warning, and a signal log (`logs/signals.csv`) that grades each logged signal 5 trading days later and compares live accuracy to the backtest. DRY_RUN unchanged and on by default.
- Cached prices (5 min) and walk-forward results (1 h): an AAPL rerun takes ~0.4 s in the browser; a cold first run ~2.3 s.

### Tried and did NOT help (harness medians; baseline = Sharpe 0.60, excess −2.0%, Brier 0.2493)
- Gradient boosting (shallow, heavily regularized): Sharpe 0.63, excess −2.6%, Brier 0.2495.
- Fewer features (6 or 4): Sharpe 0.59–0.64 but Brier worse (0.2497–0.2533) and fewer tickers beat the base rate (5–11 / 30).
- Predicting excess return vs SPY: much worse — Sharpe 0.37–0.50, excess CAGR −7% to −9%.
- Volatility-targeted sizing (no leverage): Sharpe unchanged (0.58–0.62), excess CAGR −7.5% to −11% because exposure shrinks.
- Cross-sectional rank features: Sharpe 0.58–0.62, excess −2.7% to −3.4%, Brier 0.2495–0.2506. (Only usable where a universe is loaded together.)
- Random forest remains available (`BASELINE_SPEC`).

### Not verified / limitations
- Live Alpaca paper orders and the positions/P&L table against a real account (no keys; tested with the demo broker, dry run only).
- Live accuracy needs weeks of graded signals before it means anything; currently 0 graded.
- Bot/CLI do not get the SPY market-regime feature; the edge rule is applied in the UI (Paper Trade shows it, bot order logic is unchanged).
- The blank moment before Streamlit's very first script run (~1–2 s on a cold page) is the framework shell and can't be removed from app code; the skeleton covers the rest.
- Survivorship bias: universe is today's large caps. CLI regression baseline was intentionally re-captured.

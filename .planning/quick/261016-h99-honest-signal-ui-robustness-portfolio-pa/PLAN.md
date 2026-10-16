# Quick 261016-h99: Honest signal UI, robustness, portfolio/paper-trade, UX polish

Step 1 (model harness, ModelSpec, minimum-edge rule, bootstrap CI fn) done in commit 1f82753.

Tasks
1. Signal card states Buy / Sell / No edge; base-rate-adjusted confidence; 3-question verdict banner.
2. Bootstrap Sharpe CI in results table; net-of-costs sensitivity chart (0/5/10/25 bps); "Results from" defaults to first OOS date, shown explicitly.
3. Portfolio: SPY + equal-weight benchmarks beside top-N.
4. Paper Trade: positions/P&L table; signal log with later outcome; live-vs-backtest accuracy. DRY_RUN stays on.
5. UX: skeleton loader on Single Ticker, consistent logo, caching, ticker autocomplete, Compare mode (<=4).
6. CHANGELOG with harness before/after + what did not help.

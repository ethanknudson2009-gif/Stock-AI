# 01 · Product — Output

**User:** The owner (Bryan) + friends/mentors he demos to. Single JTBD: "Run and
inspect a paper-trading bot end-to-end so I learn how these systems really work."

## v1 user stories
- As the owner, I want to backtest a single ticker in the browser, so that I can see honest OOS vs in-sample results. **[Done — Phase C]**
- As the owner, I want to backtest a top-N portfolio across a universe, so that I can judge a cross-sectional strategy with a real portfolio Sharpe. **[Done — Phase D]**
- As the owner, I want the bot to place daily EOD paper orders via Alpaca, so that the core loop runs for real (sandbox). **[Phases E–G]**
- As the owner, I want to swap the model (RandomForest ↔ Jev) behind one interface, so that I can compare signals. **[Phase A done; Jev = Phase H]**

## Acceptance criteria (high level)
- Backtests separate OOS from in-sample and disclose survivorship bias.
- Secrets never appear in the UI or logs.
- Paper orders are idempotent (no duplicate fills on re-run) and default to DRY_RUN.

## Non-goals (v1)
Real-money trading · intraday · options/crypto · a risk engine · multi-user hosting.

## Done when
A scheduled EOD run places paper orders from model signals, and the backtest explorer
renders both single- and multi-ticker results honestly.

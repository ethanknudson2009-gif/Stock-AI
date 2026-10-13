# Glossary

- **EOD** — End of day. Signals are generated on daily close data.
- **OOS (out-of-sample)** — Performance on held-out data the model never trained on. The honest number.
- **In-sample** — Performance on training data; flattering and overfitting-prone. Shown only for contrast.
- **SignalBackend** — The Protocol every model (RandomForest, Jev) conforms to: `fit`, `predict_proba_up`, `name`.
- **Cross-sectional** — Ranking many tickers against each other on the same day, then holding the top N.
- **Portfolio Sharpe** — Risk-adjusted return computed on the combined daily portfolio-return series (NOT an average of per-ticker Sharpes).
- **Top-N** — The N highest-probability tickers held equal-weight, rebalanced daily.
- **Survivorship bias** — Backtesting on today's universe hides companies that failed/delisted; inflates past returns.
- **bps** — Basis points. 1 bp = 0.01%. Per-trade cost assumption (default 10 bps).
- **Jev** — TypeSafe AI's 2026 classifier; the intended signal model for v1 (Phase H).
- **Alpaca paper** — Alpaca's sandbox broker; real order plumbing, fake money.
- **FakeBroker** — In-memory broker used for tests before the real Alpaca adapter (Phase E).

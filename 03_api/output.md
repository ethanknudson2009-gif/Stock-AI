# 03 · API — Output

## SignalBackend (internal Protocol) — `stock_ai/models/base.py`
- `name: str`
- `fit(X: DataFrame, y: Series) -> None`
- `predict_proba_up(X: DataFrame) -> Series`  # P(up) in [0,1], index-aligned to X
Feature columns are the single source of truth: `FEATURE_COLUMNS` in `classifier.py`.

## Broker Protocol (Phase E, planned)
- `get_positions() -> dict[str, float]`
- `submit_order(ticker: str, target_weight: float) -> Order`  # idempotent per (day, ticker)
- `cancel_all() -> None`
- `FakeBroker` (in-memory, tested) and `AlpacaPaperBroker` (Phase F) both conform.

## External surfaces
- **yfinance** — `fetch_price_history(ticker, start, end)`; raises `ValueError` on empty.
- **Alpaca paper** — hard-assert the PAPER base URL; pre-flight asset check; TimeInForce
  policy decided in Phase F. Never the live endpoint in v1.
- **TypeSafe / Jev** — pinned exact-minor (young SDK, breaking minors); mock HTTP in tests.

## Boundary rules
Fail fast with a specific `ValueError` naming the bad value · wrap broker/model calls so
a thrown error is scrubbed of key material before it surfaces (`Settings.scrub`) ·
`showErrorDetails = false` in Streamlit.

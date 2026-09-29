# External Integrations

**Analysis Date:** 2026-09-29

## APIs & External Services

**Market Data:**
- Yahoo Finance (via `yfinance` package) - Sole source of OHLCV price history
  - SDK/Client: `yfinance.download()` called in `stock_ai/data/loader.py:9`
  - Auth: none required (yfinance's public/unofficial Yahoo Finance endpoint)

**Brokerage / Paid Data (planned, not implemented):**
- Alpaca - Referenced only in `.env.example` as a future option ("Optional: only needed if you swap yfinance for a paid data/broker API")
  - Auth env vars: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` (both commented out, unused)
  - No Alpaca SDK is in `requirements.txt` and no code references it — this is aspirational/documented-only, not a live integration

## Data Storage

**Databases:**
- None. No ORM, no DB client, no connection strings anywhere in the codebase.

**File Storage:**
- Local filesystem only, and even that is not currently implemented in code:
  - `.gitignore` reserves `data/raw/`, `data/cache/`, `*.csv`, `*.parquet`, and `models/*.pkl|.pt|.joblib` paths for future caching/model-artifact persistence, but no code in `stock_ai/data/loader.py` or `stock_ai/models/classifier.py` writes to these paths yet — every run re-fetches from Yahoo Finance and retrains from scratch in memory.

**Caching:**
- None implemented (see above — `data/cache/` is gitignored but unused by current code)

## Authentication & Identity

**Auth Provider:**
- None — this is a single-user local CLI tool with no auth layer

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, no error-tracking SDK)

**Logs:**
- `print()` statements only, in `main.py` (`cmd_fetch`, `cmd_train`, `cmd_backtest`) — no logging framework configured

## CI/CD & Deployment

**Hosting:**
- None — run locally via `python main.py <command>`

**CI Pipeline:**
- None detected (no `.github/workflows/`, no other CI config)

## Environment Configuration

**Required env vars:**
- None required for current functionality (yfinance needs no key)
- Optional/future: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` (documented in `.env.example`, not yet consumed by any code)

**Secrets location:**
- `.env` file (gitignored, not present in repo) — would hold the above Alpaca keys if/when that integration is built. `python-dotenv` is installed but not yet wired up to load `.env` anywhere in the codebase.

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

---

*Integration audit: 2026-09-29*

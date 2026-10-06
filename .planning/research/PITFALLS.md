# Domain Pitfalls — Stock-AI v1 Milestone

**Domain:** Automated paper-trading bot + Streamlit backtest explorer (daily EOD, multi-ticker US equities, Jev + RandomForest, Alpaca paper)
**Researched:** 2026-10-06
**Confidence:** HIGH on Alpaca/Streamlit/multi-ticker pitfalls (well-documented in SDK docs, Streamlit docs, quant literature); MEDIUM on Jev-specific pitfalls (young 2026 SDK, inferred from TypeSafe docs + openclawdatabase + release-note patterns).
**Phase legend:** A=SignalBackend Protocol · B=Config/Universe · C=Streamlit single-ticker · D=Multi-ticker · E=Broker Protocol · F=Alpaca adapter · G=EOD bot loop · H=Jev adapter

---

## Critical Pitfalls (HIGH severity for a solo-beginner mentor demo)

### Pitfall 1: Hitting the LIVE Alpaca endpoint by accident
**Phase:** F · **Severity:** HIGH
**What goes wrong:** `TradingClient(api_key, secret_key)` without the `paper=True` keyword defaults to live-trading base URL for keys from a live account; same for an environment variable `APCA_API_BASE_URL` leaking in from a shell profile. A user with both paper and live keys in `.env` can submit real orders thinking they're paper.
**Warning signs:** Account page shows real cash balance, order confirmations arrive from an address like `trade-notifications@alpaca.markets` not `paper-trade-notifications@`, `trading_client._base_url` ends with `api.alpaca.markets` instead of `paper-api.alpaca.markets`.
**Prevention:**
- `AlpacaPaperBroker.__init__` passes `paper=True` AND asserts `"paper-api" in self._client._base_url` on construction — fail-loud if the SDK ever reinterprets `paper=True`.
- Only `.env` key named `ALPACA_API_KEY` (paper), reject any key starting with `AK` that isn't paper-prefixed if Alpaca ever adds a prefix convention.
- pytest test: construct `AlpacaPaperBroker`, assert `paper-api.alpaca.markets` in base URL. This test is non-negotiable.
- Never read `APCA_API_BASE_URL` from env; always pass `paper=True` explicitly so SDK ignores the env override.
**Detection:** Add a Streamlit banner on the Account page: `BROKER: paper-api.alpaca.markets` in green, red if anything else.

### Pitfall 2: Non-idempotent order submission (double-fill on Streamlit rerun or re-click)
**Phase:** G · **Severity:** HIGH
**What goes wrong:** Streamlit reruns the entire script on every widget interaction. If the "Submit" button handler calls `broker.submit_order(...)` without a `client_order_id`, every rerun that re-enters the handler state (e.g. user clicks something else before dismissing a toast) submits again. Same risk if a cron re-fires `bot.py` after a transient failure.
**Warning signs:** Alpaca account shows 2–3 identical orders at same price, "duplicate position" errors in logs, trade log CSV has repeated rows with identical timestamps rounded to the minute.
**Prevention:**
- Every `Order` carries a deterministic `client_order_id` keyed on `{YYYY-MM-DD}_{ticker}_{side}` (date in US/Eastern, not UTC — see Pitfall 7). Alpaca enforces per-account uniqueness and rejects duplicates with a clear 422.
- `AlpacaPaperBroker.submit_order` catches the 422-duplicate response and returns the existing order id as a no-op instead of raising — true idempotent semantics.
- Two-step UI: "Preview" button computes orders and stashes them in `st.session_state["pending_orders"]`; "Confirm" button submits and immediately clears the key.
- pytest with `FakeBroker` asserting: calling `submit_order` twice with same `client_order_id` records only one submission.
**Detection:** Daily report that groups orders by `client_order_id` prefix — any count > 1 is a bug.

### Pitfall 3: Averaging per-ticker Sharpe ratios instead of computing a portfolio Sharpe
**Phase:** D · **Severity:** HIGH
**What goes wrong:** It is tempting to run `run_backtest()` per ticker, then report `mean([sharpe_i for i in tickers])`. This is mathematically wrong and inflates the reported Sharpe by roughly `sqrt(N_uncorrelated_tickers)` relative to the true number. A mentor will spot this in 10 seconds.
**Warning signs:** Reported Sharpe > 3 on a 50-ticker long-only momentum portfolio with 10bps costs; Sharpe barely changes when you flip the model to random; headline Sharpe > any individual ticker's Sharpe.
**Prevention:**
- `multi_engine.run_portfolio_backtest` computes a **portfolio return series**: for each date `t`, `portfolio_return[t] = Σ_i weight_i[t] * return_i[t+1]` where `weight_i[t] = 1/N` for `i ∈ chosen_top_N` else 0.
- Sharpe = `mean(portfolio_return) / std(portfolio_return) * sqrt(252)`. Not `mean(per_ticker_sharpes)`.
- Include turnover costs on weight changes between `t-1` and `t`.
- pytest: construct 3 synthetic tickers with known returns and known top-N selection; assert portfolio-return math matches hand-calculated series to within float tolerance. Also assert the result is NOT equal to `mean(per_ticker_sharpes)` on a non-degenerate example.
- UI must label the metric "Portfolio Sharpe (equal-weight top-N, daily rebalance)" — never bare "Sharpe".
**Detection:** Sanity check — on a totally random signal, portfolio Sharpe should be ~0 ± a few tenths. If random signals produce Sharpe 1.5+, the math is wrong.

### Pitfall 4: Survivorship bias in the universe
**Phase:** B, D · **Severity:** HIGH
**What goes wrong:** The default universe is "today's 50 liquid US tickers" (e.g. current S&P members). Backtesting that fixed list on 2015–2026 data silently excludes every company that got delisted, acquired, or dropped out — all failures are missing. Resulting backtests overstate returns by 2–4% annualized on long horizons.
**Warning signs:** Backtest returns look suspiciously higher than SPY on long windows; universe has no financial-crisis-era losers (no WAMU, no LEH, no SVB-style blowups post-2023); all tickers happen to have continuous data back to the start date.
**Prevention:**
- Document explicitly in `universe/tickers.py` docstring: "This is a *current* universe snapshot. Backtests are survivorship-biased by construction. For honest historical research, use a point-in-time index membership source — out of scope for v1."
- Keep the backtest date range short (e.g. default last 3 years) so bias is bounded.
- Add a benchmark overlay (SPY) in the UI — it also has survivorship effects but comparable ones.
- Note the bias in the README and in a tooltip on the UI's "Portfolio Sharpe" metric.
- v2 differentiator: integrate a point-in-time index membership feed.
**Detection:** If backtest beats SPY by 10%+/yr with simple RSI+SMA features, suspect survivorship bias (or a leak) before celebrating.

### Pitfall 5: Data alignment errors across tickers (NaN, misaligned dates, holidays)
**Phase:** D · **Severity:** HIGH
**What goes wrong:** `yfinance` returns per-ticker DataFrames whose date indices may not perfectly align: new listings start late, delisted tickers end early, some ADRs have off-day holidays, some fields come back as `NaN` for low-volume days. Concatenating with `pd.concat(axis=1)` without `.align()` or `.reindex()` produces a DataFrame where `return_i[t]` for ticker A pairs with `return_j[t]` for ticker B that is actually the *prior* trading day's return — a silent lookahead for A, lag for B.
**Warning signs:** Portfolio return series has NaN days you don't expect; cross-sectional ranker occasionally picks a ticker with suspiciously stale proba; metrics change when you add/remove a single ticker from the universe.
**Prevention:**
- One canonical trading-day index: use `pandas_market_calendars` NYSE calendar or SPY's date index as the reference. Reindex every ticker to that calendar; forward-fill ONLY within reasonable gaps (<2 days) and drop longer gaps.
- Enforce in `multi_engine`: `assert all(ticker_df.index.equals(reference_index) for ticker_df in ticker_dfs.values())` before computing portfolio return.
- Rank only on dates where ALL universe members have valid features — or explicitly carry forward last valid rank with a logged warning.
- pytest with a synthetic universe where one ticker has holidays or NaNs; assert portfolio-return math either excludes that date or handles it deterministically.
**Detection:** Count of NaN rows in the portfolio return series logged on every backtest run. If > 1% of rows, investigate.

### Pitfall 6: Streamlit reruns re-fetching + re-training on every widget change (UI feels broken)
**Phase:** C · **Severity:** HIGH
**What goes wrong:** Streamlit reruns the entire `app.py` script top-to-bottom on every widget interaction (slider move, radio click, text input). Without caching, every tiny slider nudge re-downloads yfinance data for 50 tickers and retrains a RandomForest. UI feels frozen for 30–120 seconds between moves; also hammers yfinance into rate-limiting.
**Warning signs:** Spinner appears constantly, mentor demo stalls after any input, yfinance returns empty DataFrames mid-session (rate-limited), browser console shows WebSocket disconnects.
**Prevention:**
- Wrap `fetch_price_history` in a `@st.cache_data(ttl=3600)` helper **inside `app.py`** (not inside `stock_ai/`). TTL of 1 hour is fine for EOD data.
- Wrap model training in `@st.cache_resource` (not `cache_data`) because models aren't picklable-friendly and we want one instance, not copies.
- Put slow widgets inside an `st.form` so interim widget changes don't trigger reruns — only "Run Backtest" button submission does.
- Use `st.fragment` (Streamlit 1.37+) for the backtest results panel so re-renders stay scoped.
- Keep `app.py` import of `stock_ai.*` cheap — no heavy top-level work.
**Detection:** Add a `print(f"[rerun] {datetime.now()}")` at top of `app.py` during development. If you see 5+ reruns per interaction, cache boundaries are wrong.

### Pitfall 7: Timezone confusion between US/Eastern market hours and local time
**Phase:** G, F · **Severity:** HIGH
**What goes wrong:** The bot runs at "EOD" but EOD *where*? Running `bot.py` at 4:05pm local time on the US West Coast fires at 1:05pm Eastern — market still open. Running at midnight UTC fires on a date that's a day ahead in Alpaca's accounting. `client_order_id = f"{date.today()}_{ticker}_buy"` uses the system's local date, which can disagree with the Alpaca trading-day date, breaking idempotency across runs that straddle midnight local vs midnight Eastern.
**Warning signs:** Orders submitted while market is still open and get fills at mid-day prices instead of close; `client_order_id` collision errors appear on legitimate first attempts of the day; signals computed on "yesterday's" bar when "today's" close is already available.
**Prevention:**
- Hard-code US/Eastern (`zoneinfo.ZoneInfo("America/New_York")`) for ALL trading-date logic. Create one helper `trading_day_today() -> date` that returns Eastern-today.
- `client_order_id` = `f"{trading_day_today().isoformat()}_{ticker}_{side}"`.
- Check `TradingClient.get_clock()` before submitting: if `clock.is_open` is True, either refuse (EOD-only policy) or submit as `TimeInForce.CLS` (market-on-close). v1 recommendation: refuse with a clear error — this is an EOD bot.
- Document in README: "Run after 4:05pm ET; the bot will refuse if market is still open."
- pytest with a frozen clock asserting `trading_day_today()` returns the right date at 11:59pm PT (which is 2:59am ET next day).
**Detection:** Log `clock.timestamp`, `trading_day_today()`, and system `datetime.now()` on every bot run. Any disagreement is a bug.

### Pitfall 8: Missing kill switch — buggy signals spray dozens of orders
**Phase:** G · **Severity:** HIGH
**What goes wrong:** Jev returns garbage (API 500, SDK bug, prompt drift) and every ticker scores 0.99 confidence. Without a cap, the bot submits 50 "buy max notional" orders. Even on paper, this (a) looks like the bot "works" when it's spraying noise (PROJECT.md Risk #2), (b) blows through Alpaca's rate limits, (c) is embarrassing in a demo.
**Warning signs:** All universe members selected, position concentration > intended, orders submitted beyond daily cap, suspiciously uniform probabilities across tickers.
**Prevention:**
- Hard-coded per-order notional cap (e.g. `MAX_ORDER_USD = 1000`) in `config/settings.py`, asserted in `execution/orders.diff()`.
- Hard-coded daily-max-orders cap (e.g. `MAX_ORDERS_PER_DAY = 10`) — count orders in `logs/orders.csv` for `trading_day_today()` and refuse to submit a new one above the cap.
- Sanity gate: if `len(chosen) == len(universe)` or `stddev(scored.values()) < 0.01`, abort with "signals look degenerate" error and log the full score dict.
- `DRY_RUN=true` env flag that short-circuits `broker.submit_order` to a log-only call. Default to `DRY_RUN=true` in `.env.example` — users must opt into live paper submission.
- `KILL_SWITCH` file: before each submission, check for existence of `KILL_SWITCH` file in repo root; if present, refuse all orders. Lets the user `touch KILL_SWITCH` to disable the bot in one command.
**Detection:** Weekly review of `logs/orders.csv`: count orders per day; any day > 10 is investigated.

### Pitfall 9: `st.secrets` vs `.env` double-source confusion
**Phase:** B, C · **Severity:** HIGH (for secret exposure, which permanently burns an API key on a public repo)
**What goes wrong:** Streamlit documentation heavily promotes `st.secrets` (reads `.streamlit/secrets.toml`). Mixing it with `python-dotenv` creates two files containing the same keys, two gitignore entries that may drift, two code paths that read config differently. Easy failure modes: `.streamlit/secrets.toml` NOT in `.gitignore` and gets committed; or Alpaca key loaded from `.env` in CLI but from `st.secrets` in UI, so a mentor edits one and nothing changes.
**Warning signs:** Two keys for the same thing; `st.secrets["ALPACA_API_KEY"]` works in UI but `os.environ["ALPACA_API_KEY"]` raises; GitHub secret-scanning email arrives.
**Prevention:**
- STACK.md decision is locked: `.env` only, `python-dotenv` only. Do NOT use `st.secrets` in v1.
- `app.py` calls `load_dotenv()` at top; all key reads go through `stock_ai/config/settings.py:load_settings()`.
- `.gitignore` includes `.env`, `.env.local`, `.streamlit/secrets.toml` (defensive, even though we don't create it).
- pre-commit hook or `make precommit` target running `git ls-files | grep -E "^\.env$|secrets\.toml$"` — fail on hit.
- README has a short "Secrets" section telling mentors exactly which file to edit.
**Detection:** `git log --all --full-history -- .env .streamlit/secrets.toml` on first push and before any public demo; if either file appears, rotate the key immediately.

### Pitfall 10: Secrets leaking in Streamlit tracebacks or logs
**Phase:** C, F, H · **Severity:** HIGH
**What goes wrong:** By default Streamlit renders unhandled exception tracebacks in the browser. If `AlpacaPaperBroker` or `JevBackend` constructs an auth header inline and the SDK logs the request on error, the API key can end up in the traceback shown to anyone looking at the screen (including over a Zoom demo).
**Warning signs:** Full request headers in error output; keys visible in `print()` debug lines; `.streamlit/logs/` contains key strings.
**Prevention:**
- `.streamlit/config.toml`: `[client]\nshowErrorDetails = false` for any demo build.
- Wrap all broker/Jev calls in a try/except in `app.py` that catches and re-raises with a redacted message (`st.error("Alpaca call failed: see server logs")`).
- `stock_ai/config/settings.py:Settings.__repr__` returns a redacted version (last-4 only).
- Never `print(settings)` or `logger.info(settings)`; log `settings.redacted()`.
- Add a pytest smoke test: construct `Settings(alpaca_key="SECRET123")`, assert `"SECRET123" not in repr(settings)`.
**Detection:** Grep `logs/` and recent `.streamlit/` logs for the last 4 chars of the actual key — should be zero hits.

---

## Moderate Pitfalls (MEDIUM severity)

### Pitfall 11: Jev SDK breaking changes between minor versions
**Phase:** H · **Severity:** MEDIUM
**What goes wrong:** Public docs explicitly warn that `typesafe-sdk` 1.x minors have shipped breaking changes to question-type schemas. `pip install -U` can rename `Choice` → `ChoiceQuestion`, change `probabilities` from a dict to a list, or require new required kwargs on `system_one`. If `requirements.txt` uses `typesafe-sdk>=1.3`, a fresh clone can get a broken 1.5.
**Warning signs:** Mentor clones repo, runs `pip install -r requirements.txt`, imports fail; `TypeError` on `.probabilities` access; model alias `jev-1.13` no longer accepted.
**Prevention:**
- Exact-minor pin: `typesafe-sdk==1.3.*` (STACK.md decision). No `>=`, no `~=` wider than minor.
- Pin model alias explicitly (`jev-1.13`, not `jev-latest`) in `jev_backend.py`.
- `JevBackend` wraps the SDK — one file to patch when the SDK breaks. Everything downstream depends only on `SignalBackend` Protocol.
- Smoke test in `tests/test_jev_backend.py` that mocks the HTTP response with a captured 2026-10 fixture and asserts the backend produces a valid Series.
- README: "Jev SDK pin. Bump deliberately with: `pip install typesafe-sdk==1.X.*` then rerun pytest."
**Detection:** CI job (even a simple `make ci` locally) that installs from `requirements.txt` fresh each run and runs the full test suite.

### Pitfall 12: Jev latency and unit-cost spikes
**Phase:** H · **Severity:** MEDIUM
**What goes wrong:** Jev is marketed for HFT/market-making but priced per-call for retail. A 50-ticker universe calls `system_one` 50 times per EOD. If each call averages 1.2s (plausible for a System One model), that's a minute of bot runtime per day — tolerable. But cost: at $0.001–$0.01/call (hypothetical for a 2026-launched model), that's $0.05–$0.50/day × 252 trading days = $12.60–$126/year. Live backtesting across 10 years of history, per-day, per-ticker, with repeated reruns during development can easily hit hundreds of calls and $$$.
**Warning signs:** Monthly bill creeps up unexpectedly; UI backtest takes 10+ minutes; `typesafe-sdk` rate-limit 429s.
**Prevention:**
- Use Jev for **live scoring only** (the latest bar). Backtest on cached historical scores or on the RandomForest baseline — do not re-score the entire 10-year history through Jev on every slider move.
- Add a `--jev` flag that is OFF by default in backtest mode; UI radio defaults to RandomForest with a visible "(uses no API credits)" caption.
- Batch calls: pass multiple feature vectors in one `system_one` call if the SDK supports it (check 1.3.x docs).
- Cache Jev responses on disk (parquet keyed by feature-vector hash + model version) so repeated backtests don't re-call.
- Budget alarm: track calls in a counter file; refuse > `JEV_DAILY_CALL_LIMIT` calls per calendar day.
**Detection:** Log every Jev call with latency and estimated cost; roll up daily totals in a small dashboard panel.

### Pitfall 13: Alpaca rate-limit (200 req/min free paper tier) exhaustion
**Phase:** F, G · **Severity:** MEDIUM
**What goes wrong:** `alpaca-py` doesn't automatically back off. A loop that fetches positions, submits an order, confirms it, polls fills for 50 tickers in rapid succession can burst past 200 req/min. Responses then 429 and the SDK raises; the bot aborts mid-rebalance leaving half-submitted orders.
**Warning signs:** `APIError: too many requests`, partial order submission in `logs/orders.csv` where today's trading_day_today() is missing some universe members.
**Prevention:**
- Serialize order submission with a small sleep (`time.sleep(0.1)` between orders → 10 req/s, well under limit).
- Fetch positions ONCE per `run_eod`, cache in-memory for the duration of the loop.
- Catch 429, back off with exponential retry (max 3 attempts).
- Transaction-aware logging: write each `(ticker, order_id)` to `logs/orders.csv` immediately after `submit_order` succeeds, so a crash mid-loop can be resumed by diffing CSV against intended orders.
**Detection:** Any 429 in logs is a bug — adjust pacing.

### Pitfall 14: Alpaca order rejections (fractional shares, non-tradable, PDT, insufficient buying power)
**Phase:** F · **Severity:** MEDIUM
**What goes wrong:** Alpaca paper enforces many of the same rules as live: a `qty=0.5` fractional request on a non-fractional-eligible ticker is rejected; `BRK.B` symbol must be `BRK/B` in some SDK versions; an ETF in liquidation is `tradable=false`; shorting without a borrow available is rejected; cash account has T+1 settlement rules even on paper for some asset classes.
**Warning signs:** `OrderRejected` with cryptic reason codes; some universe tickers consistently fail silently; buying power seems lower than cash.
**Prevention:**
- Before submission, call `trading_client.get_asset(symbol)` and check `asset.tradable` and `asset.fractionable`. Floor to integer shares in `orders.diff()`.
- Normalize ticker symbols: a small `normalize_symbol(ticker)` helper that handles `BRK.B` → `BRK/B` etc. Document the quirks in the function.
- Catch `APIError` from `submit_order`, log the rejection reason, continue with other orders instead of aborting.
- Pre-flight check in the "Preview" step: fetch `get_clock`, `get_account`, and `get_asset` for every ticker; surface warnings in the UI table BEFORE the confirm button.
- Don't short in v1 (long/flat only — already in strategy/signal.py).
**Detection:** Rejection reason summary at end of each bot run; any new reason code should prompt a code review.

### Pitfall 15: Extended-hours / after-hours order semantics
**Phase:** F, G · **Severity:** MEDIUM
**What goes wrong:** `TimeInForce.DAY` orders submitted after 4pm ET are queued for the NEXT trading day's open — not filled at today's close. For an EOD bot, the user may *think* they're trading at today's close but actually filling at tomorrow's open, which is a different price and breaks the backtest ↔ live comparison.
**Warning signs:** Fills always at the next day's open price; `fill_price` is not close to the previous `close` on signal day.
**Prevention:**
- Policy decision for v1: trade at NEXT OPEN (simpler, consistent) using `TimeInForce.OPG` (market-on-open for next session) OR trade at TODAY's close using `TimeInForce.CLS` (market-on-close, submitted before ~3:50pm ET).
- Document the choice clearly in README and align the backtest engine to match. If signals use today's close, execution should also use today's close (CLS); if execution uses tomorrow's open, backtest returns should be computed open-to-open.
- Reject order submission between 4:00pm and 4:00am ET if policy is CLS (window closed); reject between 9:30am and 3:45pm ET if policy prohibits intraday (any `is_open=True`).
- v1 recommendation: next-day open. Simpler timing, no race against 3:50 cutoff, easier to reconcile backtest.
**Detection:** Compare backtest-assumed fill prices vs actual Alpaca fill prices in a reconciliation report.

### Pitfall 16: Streamlit `st.session_state` reset on page refresh
**Phase:** C · **Severity:** MEDIUM
**What goes wrong:** `st.session_state["pending_orders"]` lives only for the browser session. If the user refreshes between "Preview" and "Confirm," the pending orders vanish and clicking "Confirm" sends nothing (good) OR a developer forgets this and the Confirm button recomputes orders inline — making Preview a lie because the recomputation may rank differently than the Preview showed.
**Warning signs:** Confirm submits different orders than what Preview showed; refreshing the page clears the preview but Confirm button stays enabled.
**Prevention:**
- Confirm button is DISABLED unless `st.session_state["pending_orders"]` exists and is non-empty.
- Confirm handler submits EXACTLY the stashed orders; it never recomputes.
- After submission, clear `st.session_state["pending_orders"]` immediately to prevent re-click.
- Show the exact pending orders in the UI next to the Confirm button so the user sees what they're confirming.
**Detection:** Manual test: Preview, refresh, verify Confirm is disabled.

### Pitfall 17: ADV (average daily volume) filter missing — bot picks illiquid names
**Phase:** B, D · **Severity:** MEDIUM
**What goes wrong:** Default universe includes small-cap names with low ADV. A $1000 order in a $5 stock with 100k ADV is 1-2% of daily volume — not catastrophic at that size, but if the bot scales or the user bumps caps, slippage will dominate returns and backtests (which assume no price impact) become fiction.
**Warning signs:** Universe includes any ticker with 30-day ADV < $5M; backtest returns heavily driven by one or two illiquid names.
**Prevention:**
- Universe curation rule in `universe/tickers.py`: default list is 20-50 names, each with 30d ADV > $50M (large-cap S&P 500 + major sector ETFs).
- Document the rule in the docstring.
- Optional: ADV check in loader — refuse to include a ticker whose last-30d `Volume * Close` mean is below `MIN_ADV_USD`.
- v2: dynamic universe filtering by liquidity.
**Detection:** Backtest-time report: top 5 tickers by contribution — are any of them illiquid?

### Pitfall 18: Universe churn not handled (ticker gets delisted mid-backtest)
**Phase:** B, D · **Severity:** MEDIUM
**What goes wrong:** A ticker in the universe is delisted at some point in the backtest range. yfinance returns a short-ended series. Portfolio math either silently drops it (optimistic — the delisting-loss is excluded) or carries NaN forward (also wrong).
**Warning signs:** Universe member's data ends before `end_date` with no error; portfolio holdings on day T include a ticker whose data stopped on day T-30.
**Prevention:**
- `multi_engine` tracks `active_universe[t] = {ticker | ticker has valid data at t}` and ranks only within active universe for day t.
- When a held ticker becomes inactive, treat the position as closing at the last available close price (bakes in some delisting penalty but is honest).
- Log every ticker that becomes inactive during the backtest window with the date.
- Document in UI: "Backtest is survivorship-biased; delisting is modeled by closing at last available price."
**Detection:** Backtest report lists tickers that went inactive and when; mentor can see the model is aware of delistings.

### Pitfall 19: Streamlit caching stale across code changes
**Phase:** C · **Severity:** MEDIUM
**What goes wrong:** `@st.cache_data` keys cache entries by function arguments and source code hash. But if the cached function imports a helper from `stock_ai/` that YOU change, Streamlit may not detect the change — the cache returns stale results until manually cleared. Common footgun: fix a feature-engineering bug, backtest still shows the old numbers.
**Warning signs:** Code change doesn't take effect in UI; metrics identical to before your fix; `Clear cache` menu action fixes it.
**Prevention:**
- During development: hit "C" or use the "Clear cache" menu button regularly.
- In `app.py`, add a sidebar "Clear cache" button calling `st.cache_data.clear()`.
- Short TTLs during dev (`ttl=60`), longer in demo (`ttl=3600`).
- Version the cached helpers: include a `cache_version: int = 1` parameter in the signature and bump when internals change.
- Don't cache functions that import from freshly-edited modules without reloading the Streamlit server (`streamlit run app.py` must be restarted after `stock_ai/` edits in some cases).
**Detection:** Deliberate test: change a feature constant, rerun UI; verify metrics change. If not, debug cache keys.

### Pitfall 20: "Trade on startup" — bot executes orders the moment it's imported
**Phase:** G · **Severity:** MEDIUM-HIGH
**What goes wrong:** `bot.py` has `run_eod()` at module top-level or inside `if __name__ == "__main__":` without any gating. A mentor imports `bot` to inspect it in a REPL, and the bot submits orders. Or `app.py` imports `bot` for a function, and the import side-effects a trading run.
**Warning signs:** Any top-level `broker.submit_order(...)` call; `from bot import ...` triggers network activity.
**Prevention:**
- `bot.py` is pure: only function definitions at module level.
- `if __name__ == "__main__":` block is the ONLY place that calls `run_eod()`.
- `run_eod()` requires explicit `broker` and `backend` parameters — no default-construction of a real `AlpacaPaperBroker` inside the function.
- `app.py` imports specific functions (`from bot import compute_todays_orders`), never `import bot`.
- pytest asserts: `import bot` must complete in < 100ms and produce no network activity (use `pytest-socket` with socket disabled by default).
**Detection:** Install `pytest-socket`, run suite with `--disable-socket --allow-unix-socket`. Any inadvertent network call fails loudly.

---

## Minor Pitfalls (LOW severity)

### Pitfall 21: Plotly chart performance on 10-year × 50-ticker series
**Phase:** C, D · **Severity:** LOW
**What goes wrong:** Plotly renders slowly in-browser past ~50k data points. A full 10-year daily chart of 50 overlays is ~125k points — chart lags, zoom stutters.
**Prevention:** Default UI backtest window = 3 years; cap chart overlays to top-5 contributors; downsample for display with `scattergl` renderer; aggregate to weekly if range > 5 years.
**Detection:** Chart feels sluggish in demo → shorten range.

### Pitfall 22: yfinance MultiIndex columns on batch download
**Phase:** B, D · **Severity:** LOW (already a known concern in CONCERNS.md)
**What goes wrong:** `yf.download(["AAPL", "MSFT"])` returns MultiIndex columns (field, ticker). `yf.download("AAPL")` returns flat columns. Code paths that stitch results together must handle both consistently.
**Prevention:** Always use the same code path. `fetch_price_history(ticker)` for single ticker; `fetch_universe_history(tickers)` for batch. Each returns a canonical shape (dict of DataFrames or long-format DataFrame — pick one). Add a test with yfinance mocked.
**Detection:** Columns' `KeyError: 'Close'` on multi-ticker fetch.

### Pitfall 23: Jev model non-determinism (same input, different output)
**Phase:** H · **Severity:** LOW
**What goes wrong:** System One models return calibrated probabilities but the exact numeric value may vary slightly between calls (sampling, temperature-like effects, server-side updates). Backtest results differ between runs; tests fail intermittently.
**Prevention:** Pin model alias (`jev-1.13`); use `seed` parameter if SDK exposes one; in tests, mock the HTTP response — do not call the live Jev API in pytest. Allow a tolerance (e.g. `abs(result - expected) < 0.05`) in integration-level assertions.
**Detection:** Flaky tests → identify and move Jev call behind the HTTP mock boundary.

### Pitfall 24: Confusing `cash` with `buying_power` in position sizing
**Phase:** F, G · **Severity:** LOW
**What goes wrong:** Alpaca accounts have both `cash` and `buying_power`. For a cash account they're ~equal; for a margin account `buying_power = cash * 2` (or 4 for day-trading). Sizing against `buying_power` on a margin account doubles position size vs intent.
**Prevention:** Explicitly use `account.cash` for v1 position sizing (long/flat, no margin by design). Document the choice. Assert `account.multiplier == '1'` on construction if the user has a cash paper account.
**Detection:** Position sizes larger than expected → check which field is being used.

### Pitfall 25: Transaction cost model drift between backtest and paper
**Phase:** D, F · **Severity:** LOW
**What goes wrong:** Backtest uses flat 10bps per trade; Alpaca paper fills at the market (zero explicit commission on Alpaca, but spread + slippage). Reported "paper performance" may differ from "backtest performance" even with the same signals — mentors asking "why don't they match?" deserve an answer.
**Prevention:** Document that backtest's 10bps is a *proxy* for spread + slippage; actual Alpaca paper has $0 commission but non-zero slippage. Reconcile periodically by computing realized cost from Alpaca fills vs backtest-assumed cost. v2 can add per-ticker spread models.
**Detection:** Paper-vs-backtest reconciliation on a sample week.

### Pitfall 26: Jev vendor lock-in via proprietary question types
**Phase:** H · **Severity:** LOW
**What goes wrong:** Writing bot logic that assumes Jev's `Choice.probabilities[answer.choice]` shape everywhere makes it hard to swap to a different provider later.
**Prevention:** `JevBackend.predict_proba_up` returns a plain `pd.Series[float]` — the Protocol boundary. Nothing downstream touches `Choice`/`Score`/`Noul` types directly. If Jev dies or gets expensive, swapping to another classifier is a one-file change.
**Detection:** `grep -r "typesafe\|jev\|Choice" stock_ai/ | grep -v jev_backend.py` should return nothing.

---

## Phase-Specific Warnings

| Phase | Topic | Likely Pitfalls | Mitigation Highlights |
|-------|-------|-----------------|----------------------|
| A — SignalBackend Protocol | Backward compat | Breaking existing tests when wrapping `RandomForestClassifier` | Keep `classifier.py` and `FEATURE_COLUMNS` as-is; `rf_backend.py` is a thin wrapper; existing tests must stay green |
| B — Config/Universe | Secrets, survivorship, ADV | #4 Survivorship, #9 st.secrets, #17 ADV, #18 Churn | `.env` only; large-cap universe only; document bias loud |
| C — Streamlit single-ticker | Reruns, caching, state, secrets in UI | #6 Rerun, #9 st.secrets, #10 Traceback leaks, #16 Session state, #19 Cache staleness | Use `st.form`, `@st.cache_data` with TTL, `showErrorDetails = false` |
| D — Multi-ticker | Portfolio math, alignment | #3 Avg-of-Sharpes, #5 Alignment, #17 ADV, #18 Churn, #21 Plot perf | True portfolio-return series; canonical trading-day index; log inactive tickers |
| E — Broker Protocol | Pure logic, idempotency contract | #2 Idempotency, #20 Startup side effects | `FakeBroker` tests enforce idempotency; pure `diff()` function |
| F — Alpaca adapter | Endpoint, rejections, settlement, timing | #1 Live endpoint, #13 Rate limit, #14 Rejections, #15 Extended hours, #24 Buying power | Hard-assert paper URL; pre-flight asset check; TimeInForce policy decision |
| G — EOD bot loop | Timezone, kill switches, duplicates | #2 Idempotency, #7 Timezone, #8 Kill switch, #20 Trade-on-startup | US/Eastern everywhere; DRY_RUN default; `KILL_SWITCH` file |
| H — Jev adapter | SDK breakage, cost, lock-in | #11 SDK breaks, #12 Cost, #23 Non-determinism, #26 Lock-in | Exact-minor pin; use Jev for live only, not full backtest; mock HTTP in tests |

---

## Verification Discipline

Each pitfall above should have at least one of:
- A pytest test that would fail if the pitfall is re-introduced (prefer this)
- A startup assertion in the relevant adapter/entry point
- A UI banner / log line that surfaces the condition to the user
- A README note aimed at mentors who clone and run the project

Minimum test coverage for v1 safety (required before mentor demo):
1. `test_paper_endpoint_assertion` — AlpacaPaperBroker refuses non-paper URL
2. `test_idempotent_submission` — FakeBroker + same client_order_id = one submission
3. `test_portfolio_sharpe_math` — 3-ticker synthetic case matches hand-calculated series
4. `test_portfolio_sharpe_not_average_of_per_ticker` — explicit anti-regression
5. `test_trading_day_timezone` — frozen clock at 11:59pm PT returns next ET date
6. `test_jev_backend_mocked_http` — recorded fixture reproduces a known Series
7. `test_bot_import_no_network` — `import bot` makes no network calls (pytest-socket)
8. `test_settings_repr_redacted` — secrets never appear in `repr(settings)`
9. `test_order_cap_enforced` — `diff()` with over-cap target returns capped order
10. `test_dry_run_short_circuit` — DRY_RUN=true means no `broker.submit_order` call

---

## Sources

- Alpaca `alpaca-py` docs — paper endpoint, `client_order_id`, `TimeInForce`, rate limits (HIGH)
- Streamlit docs — `st.cache_data`, `st.session_state`, `st.secrets`, `st.form`, `showErrorDetails` (HIGH)
- openclawdatabase.com + llmreference.com + composio.dev on TypeSafe Jev — SDK breakage history, model aliases (MEDIUM — young SDK, inferred from release notes)
- `.planning/PROJECT.md` — risk register (Risk #1 Jev, Risk #2 no-risk-layer)
- `.planning/codebase/CONCERNS.md` — existing debt (yfinance MultiIndex, RSI div-by-zero)
- `.planning/research/STACK.md` — `.env`-only secret policy, exact-minor Jev pin
- `.planning/research/FEATURES.md` — idempotency, portfolio Sharpe, DRY_RUN, kill-switch flags
- `.planning/research/ARCHITECTURE.md` — phase ordering A–H, `FakeBroker` testing pattern
- Lopez de Prado "Advances in Financial ML" — survivorship, alignment, portfolio Sharpe discipline (MEDIUM — classical reference)
- Freqtrade / Backtrader community wisdom — DRY_RUN, kill-switch, order log patterns (MEDIUM)

---

*Pitfall research for Stock-AI v1 milestone. 2026-10-06.*

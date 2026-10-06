# Technology Stack — v1 Milestone Additions

**Project:** Stock-AI (Jev-powered paper-trading bot)
**Researched:** 2026-10-06
**Scope:** NEW dependencies to add on top of the existing Python 3.12 / pandas / numpy / scikit-learn / yfinance / pytest stack. The existing stack is NOT re-researched here — see `.planning/codebase/STACK.md` for its snapshot.
**Overall confidence:** MEDIUM-HIGH (Streamlit/Plotly/alpaca-py are well-established; Jev SDK is young and has a documented history of breaking changes between minor versions — pin tightly.)

---

## Recommended Stack (Additions Only)

### UI Layer

| Technology | Version | Purpose | Why |
|---|---|---|---|
| `streamlit` | `>=1.58,<2.0` | Browser-based backtest explorer (`streamlit run app.py` → `localhost:8501`) | Fastest path to a dashboard a beginner can own and extend; zero HTML/JS; drops directly on top of pandas DataFrames; stable 1.x API through 2026. v1.58 (May 2026) is a good floor — adds `parallel=True` for `@st.fragment` which helps if we later run per-ticker backtests concurrently. |
| `plotly` | `>=6.6,<7.0` | Interactive price charts with buy/sell markers; equity-curve overlays | Required by PROJECT.md ("price chart with buy/sell markers"). Plotly's `go.Candlestick` + `go.Scatter` with marker symbols is the de facto pattern for trade-marker charts in Streamlit. Cap below 7.0: 7.0 is in `extra-testing` on Arch as of Aug 2026, not yet widely proven; stay on the 6.x series for reproducibility. |

**Explicitly NOT using:**
- `matplotlib` for the UI — kept in `requirements.txt` as a legacy/CLI-plotting dep, but Streamlit + Plotly is the mandated path for the explorer. Static matplotlib charts in a Streamlit app lose interactivity (no hover, no zoom).
- `dash` — overkill, heavier, no advantage over Streamlit for a solo beginner project.
- `gradio` — ML-demo oriented; weaker for the "parameter form + results table + chart" shape we need.
- `bokeh` — fine but Plotly has broader Streamlit idioms and more Stack Overflow answers for a beginner.

**Confidence:** HIGH — both libraries have multi-year track records and are the obvious choice for this shape of app.

---

### Broker Integration

| Technology | Version | Purpose | Why |
|---|---|---|---|
| `alpaca-py` | `>=0.43,<0.50` | Official Alpaca SDK — paper trading orders, account state, positions | Latest stable is 0.43.4 (released April 2026). Official SDK, actively maintained by Alpaca, Python 3.10+ (compatible with our 3.12). Provides `TradingClient(paper=True)` which is exactly the paper-sandbox endpoint we need. Cap under 0.50 because alpaca-py is still pre-1.0 — minor bumps have historically shuffled request-model class names; pin to a narrow band and bump deliberately. |

**Auth pattern (prescribed):**
```python
# stock_ai/brokers/alpaca_client.py
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

load_dotenv()  # reads .env in project root

def get_trading_client() -> TradingClient:
    key = os.environ["ALPACA_API_KEY"]
    secret = os.environ["ALPACA_SECRET_KEY"]
    return TradingClient(api_key=key, secret_key=secret, paper=True)  # paper=True is non-negotiable in v1
```

**Explicitly NOT using:**
- `ib_insync` (Interactive Brokers) — requires a locally-running TWS/IB Gateway process, has a Windows-biased install story, and no free paper account that works for US retail without extra signup friction. Alpaca is the lower-friction choice for a solo beginner on macOS.
- `alpaca-trade-api` (the old SDK) — DEPRECATED. Alpaca officially migrated users to `alpaca-py`. Do not install both; they will collide on `from alpaca...` imports.
- The raw REST API via `requests` — pointless when the official SDK handles pagination, retries, and typed response objects.

**Confidence:** HIGH — official SDK, verified usage pattern, matches PROJECT.md's "Alpaca paper" locked decision.

---

### AI Signal Classification (Jev)

| Technology | Version | Purpose | Why |
|---|---|---|---|
| `typesafe-sdk` | `==1.x.y` (pin exact minor; **do not use `>=`**) | Jev API client — feature vector → typed `Choice` (long/flat) + confidence | The only official Python SDK for Jev (TypeSafe AI's System One Model, launched Sept 2026). Returns Pydantic-validated `Choice`/`Score`/`Noul` answers with probabilities — a near-perfect shape for a signal classifier that must emit a direction + a confidence number our existing threshold logic already consumes. |

**Version policy for `typesafe-sdk` — this is the single biggest supply-chain risk in this milestone:**
- Public sources (openclawdatabase.com, LLM reference pages) explicitly warn: *"Only the early SDK releases exist so far, and minor versions have already introduced breaking changes to the question types."*
- **Do not use `>=` ranges.** Pin to an exact minor (e.g. `typesafe-sdk==1.3.*`) in `requirements.txt`, and separately pin the Jev model via the SDK's version alias (prefer `jev-1.13` or a pinned numeric alias over `jev-latest`).
- When bumping, do it in its own commit and re-run the full pytest suite + a known-answer backtest before merging.

**Auth pattern (prescribed):**
```python
# stock_ai/models/jev_client.py
import os
from dotenv import load_dotenv
from typesafe import TypeSafeClient  # import path per 2026 docs
from typesafe.questions import Choice

load_dotenv()

def get_jev_client() -> TypeSafeClient:
    # SDK reads TYPESAFE_API_KEY from env by default; pass explicitly for clarity
    return TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"])

def classify_signal(client: TypeSafeClient, features: dict) -> tuple[str, float]:
    """Returns (direction, confidence) where direction ∈ {'long','flat'}."""
    resp = client.system_one(
        state=features,  # pass computed indicator features as the state blob
        questions={
            "direction": Choice(
                description="Given today's indicators, should we go long tomorrow or stay flat?",
                options=["long", "flat"],
            )
        },
        model="jev-1.13",  # pin model version alongside SDK version
    )
    answer = resp.choices["direction"]
    return answer.choice, answer.probabilities[answer.choice]
```

**Access route:** direct TypeSafe API (`https://api.typesafe.ai/v1/systemone`). Do NOT route through OpenRouter, Vercel AI Gateway, or Cloudflare AI Gateway in v1 — they add a second credential surface, a second failure mode, and a second rate-limit layer for no v1 benefit. If direct access ever becomes an issue, OpenRouter's `jev-1.13` alias is the escape hatch.

**Explicitly NOT using:**
- `openai`/Anthropic/other LLM SDKs for the classification path — Jev is a *System One* model that returns calibrated probabilities over an enum. An LLM chat completion returning a token like "long" is a strictly worse signal source: no calibrated confidence, no cheap batched inference, no typed response. (LLMs may still be relevant for v2 news/filings sentiment, but that is out of scope here.)
- `jev-cli` on PyPI — this is a CLI wrapper, not a library; it's not the integration point we need.

**Confidence:** MEDIUM. The SDK exists and the shape fits our need. But: (1) the SDK is young and breaks between minors — real risk, mitigated by pinning; (2) PROJECT.md Risk #1 already acknowledges Jev may not deliver useful EOD-direction signals — this is a learning project, so unknown-but-pinned is acceptable.

---

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---|---|---|---|
| `python-dotenv` | `>=1.0` *(already in requirements.txt — now actually wire it up)* | Load `.env` into `os.environ` at process start | Call `load_dotenv()` once at the top of `main.py` and once at the top of `app.py`. This dep is currently dead per `.planning/codebase/STACK.md`; the Alpaca + Jev integrations are the trigger to activate it. |
| `pytest` | `>=8.0` | Test runner (already in use, now add to requirements) | Promote from implicit-dev to listed dep. Add `pytest-mock` if we end up mocking the Alpaca client; otherwise `unittest.mock` from stdlib is enough. |
| `requests` | *(transitively pulled by `typesafe-sdk` and `alpaca-py`)* | HTTP client | Do not add directly — rely on transitives. If a direct need appears, add it explicitly. |

**Deliberately NOT adding in v1:**
- `pandas-ta` / `TA-Lib` — our hand-rolled SMA/RSI in `stock_ai/features/indicators.py` is sufficient and already tested. Adding a 3rd-party indicator lib widens the surface area without unlocking a v1 requirement.
- `joblib` for model persistence — PROJECT.md explicitly defers model persistence to v2.
- `fastapi` / `uvicorn` — Streamlit is the UI; no separate API server needed for a single-user local tool.
- `redis` / `sqlite` / any DB — v1 has no persistence requirement; state lives in memory per run.
- `celery` / `rq` / `apscheduler` — v1 is "click a button to place today's orders," not a daemon. Scheduling (cron / launchd / GitHub Actions) is a v2 concern.

---

## Composition With Existing Stack

The new deps slot in cleanly:

| Existing component | How new deps compose |
|---|---|
| `stock_ai/data/loader.py` (yfinance) | **Unchanged.** Streamlit calls it with user-provided ticker/date-range inputs. |
| `stock_ai/features/indicators.py` | **Unchanged.** Its DataFrame output becomes either (a) scikit-learn's input (existing path) or (b) the `state=` dict for `TypeSafeClient.system_one()` (new path). Add a thin adapter `features_to_jev_state(df_row) -> dict`. |
| `stock_ai/models/classifier.py` (RandomForest) | **Unchanged.** Kept as the baseline per PROJECT.md Risk #1 — Jev vs RandomForest side-by-side comparison is a hard v1 requirement. |
| `stock_ai/strategy/signal.py` (confidence threshold) | **Reused as-is for Jev.** Jev returns `probabilities[answer.choice]` which plugs into the same `prob > threshold` logic the RandomForest path already uses. This is a nice architectural win — the threshold layer is model-agnostic. |
| `stock_ai/backtest/engine.py` | **Unchanged.** Takes a signal series regardless of source. Multi-ticker cross-sectional ranking is a new module (`stock_ai/strategy/ranker.py`) that sits above this engine, not inside it. |
| `tests/` (pytest) | **Extended.** Add tests that mock the Alpaca `TradingClient` and the `TypeSafeClient` so CI never calls out to real APIs. Golden-answer tests for the ranker. |
| `main.py` (argparse CLI) | **Extended** with `paper-trade` subcommand that reads today's signals and submits orders. Streamlit's `app.py` is a parallel entrypoint, not a replacement. |

---

## Environment Variables & Secrets

Extend the existing `.env.example` pattern (currently has `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` commented out). v1 version:

```bash
# .env.example — copy to .env, fill in, never commit .env

# --- Alpaca paper trading (required for paper-trade and the Paper Account UI page) ---
ALPACA_API_KEY=your_paper_key_here
ALPACA_SECRET_KEY=your_paper_secret_here
# Paper endpoint is selected by passing paper=True to TradingClient; do NOT override the base URL.

# --- Jev / TypeSafe AI (required for the Jev signal mode) ---
TYPESAFE_API_KEY=your_typesafe_key_here
# Optional: pin a specific Jev model alias; defaults to the version pinned in jev_client.py
# TYPESAFE_JEV_MODEL=jev-1.13
```

**Rules:**
1. `.env` stays in `.gitignore` (already is). Audit `.gitignore` once as part of the milestone — PROJECT.md calls this out.
2. `load_dotenv()` is called exactly once per process entry point (`main.py`, `app.py`). Do not sprinkle it through modules.
3. Modules read via `os.environ["KEY"]` (fail-loud `KeyError`), not `os.environ.get("KEY")` (fail-silent `None`). If a key is missing, the user needs to know immediately, not get a `NoneType has no attribute` three stack frames deep.
4. For Streamlit specifically, do NOT use `st.secrets` in v1. `st.secrets` wants its own `.streamlit/secrets.toml` and we'd end up with two secret stores. One `.env`, one `load_dotenv()`, one source of truth.
5. Never log secret values. If logging the Alpaca config for debugging, show only the last 4 chars of the key.

---

## Full requirements.txt (prescribed)

```
# Core data stack (unchanged)
pandas>=2.2
numpy>=1.26
yfinance>=0.2
scikit-learn>=1.5

# Config (now actually used)
python-dotenv>=1.0

# UI (new)
streamlit>=1.58,<2.0
plotly>=6.6,<7.0

# Broker (new)
alpaca-py>=0.43,<0.50

# AI signal classification (new, pinned tightly — see STACK.md Jev section)
typesafe-sdk==1.3.*

# Dev
pytest>=8.0

# Legacy — kept for any CLI-only matplotlib callers; may be removed when audited
matplotlib>=3.9
```

**Install order sanity check:** on a fresh clone, `pip install -r requirements.txt` inside a Python 3.12 venv should install cleanly on macOS without needing any system libraries beyond what the existing stack already needs (yfinance, pandas, sklearn). No TA-Lib C deps, no node, no Rust toolchain.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|---|---|---|---|
| UI framework | Streamlit | Dash / Gradio / FastAPI+React | Streamlit wins on beginner-friendliness and tight pandas integration; others add complexity without unlocking a v1 requirement. |
| Charts | Plotly | matplotlib / bokeh / altair | Plotly interactivity (hover, zoom) matters for buy/sell markers on long time series; matplotlib is static; altair is nice but Plotly has more Streamlit-specific tutorials. |
| Broker SDK | `alpaca-py` | `alpaca-trade-api` (deprecated) / `ib_insync` / raw REST | Deprecated / wrong broker / reinventing the SDK. |
| AI model | Jev (`typesafe-sdk`) | OpenAI/Anthropic chat completions | Jev returns calibrated probabilities over a typed enum, which is literally the shape of a classifier. Chat completions are the wrong tool for a signal pipeline. (This decision is also locked in PROJECT.md.) |
| Secrets | `.env` + `python-dotenv` | `st.secrets` / 1Password / AWS SSM | Single source of truth; already in `.env.example`; project is single-user local. |
| Scheduler | None in v1 (manual trigger) | APScheduler / cron / GitHub Actions | v1 is "click to trade"; automation is v2+. |

---

## Known Risks With the Chosen Stack

1. **`typesafe-sdk` breaking changes.** Documented pattern of breakage between minor versions. **Mitigation:** exact-minor pinning, pin Jev model alias, add a smoke test that calls `system_one()` with a canned fixture before any paper-trading run.
2. **Alpaca-py pre-1.0 API shifts.** Historical minor-version renames of request models. **Mitigation:** narrow version range, isolate all Alpaca imports in `stock_ai/brokers/alpaca_client.py` so a future rename is a single-file edit.
3. **Streamlit `st.rerun` footguns.** Streamlit reruns the whole script on any interaction. A naive implementation will re-fetch yfinance data and re-train the RandomForest on every slider move. **Mitigation:** wrap data loading in `@st.cache_data` (default TTL fine for EOD) and model training in `@st.cache_resource`. This is non-optional; without it the UI will feel broken.
4. **Secret leakage in Streamlit tracebacks.** Streamlit shows tracebacks in the browser by default. **Mitigation:** set `client.showErrorDetails = false` in `.streamlit/config.toml` for any config that might contain secrets, or wrap Alpaca/Jev calls in try/except that redact the key before re-raising.

---

## Sources

- [alpaca-py on PyPI (latest 0.43.4, April 2026)](https://pypi.org/project/alpaca-py/)
- [alpaca-py GitHub](https://github.com/alpacahq/alpaca-py)
- [Alpaca Trading API docs — alpaca-py](https://docs.alpaca.markets/docs/alpaca-py-trading-api)
- [Streamlit 2026 release notes](https://docs.streamlit.io/develop/quick-reference/release-notes/2026)
- [Streamlit 1.62.0 announcement (Aug 2026)](https://discuss.streamlit.io/t/version-1-62-0/122303)
- [Plotly Python 6.9.0 (July 2026)](https://archlinux.org/packages/extra/any/python-plotly/)
- [TypeSafe Jev — Netlify AI Gateway changelog (Sept 2026 launch)](https://www.netlify.com/changelog/typesafe-jev-ai-gateway/)
- [Jev Setup — SDK, OpenRouter, first call, version pinning (2026)](https://openclawdatabase.com/jev/setup/)
- [How to use Jev with Python — flaviocopes](https://flaviocopes.com/jev-python/)
- [LLM Reference — TypeSafe Jev](https://www.llmreference.com/provider/typesafe-ai/jev)
- [TypeSafe Jev Guide — Composio](https://composio.dev/content/typesafe-jev-guide-and-best-practical-usecases)

---

*Research: 2026-10-06. Confidence: HIGH for Streamlit/Plotly/alpaca-py; MEDIUM for `typesafe-sdk` (young SDK, known-breaking minors — mitigated by pinning).*

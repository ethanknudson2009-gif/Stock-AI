# Phase C — Streamlit Single-Ticker Explorer — Plan 01 SUMMARY

**Completed:** 2026-10-13
**Requirements satisfied:** UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08

## What shipped

- `app.py` (project root) — `streamlit run app.py` → localhost:8501 (UI-01).
  - Sidebar `st.form` with ticker, start/end date, cost (bps) slider, confidence-threshold slider, and a RandomForest / Jev backend selector; backtest runs only on submit (UI-02, UI-03).
  - `@st.cache_data(ttl=3600)` on price fetch + features; `@st.cache_resource` on model training — no re-fetch/re-train on widget nudges (UI-04, Pitfall #6).
  - Results: test accuracy, strategy return, buy & hold, Sharpe, max drawdown, trade count (UI-05). Out-of-sample shown prominently; in-sample tucked in a labeled expander (UI-06).
  - Plotly `Scattergl` close-price chart with triangle-up buy / triangle-down sell markers on the test slice (UI-07).
  - Jev option shows a "coming in Phase H" warning and falls back to RandomForest.
- `.streamlit/config.toml` — `showErrorDetails = false` (UI-08, Pitfall #10); `headless = true`.
- Secret safety: `load_dotenv()` called once in `app.py` (Pitfall #9); backtest wrapped in try/except that runs `Settings.scrub()` on the message so a key can't reach the browser.
- `stock_ai/backtest/engine.py` — added `max_drawdown` (peak-to-trough, negative fraction) to results.
- `stock_ai/config/settings.py` — added `Settings.scrub(text)` helper.
- `requirements.txt` — `streamlit>=1.58,<2.0`, `plotly>=6.6,<7.0`.

## Tests

`test_backtest.py::test_max_drawdown_measures_peak_to_trough` and
`test_config.py::{test_settings_scrub_removes_secret_from_error_text,test_streamlit_config_hides_error_details}`.
**21 passed.** Streamlit UI itself is not unit-tested (per ROADMAP: underlying logic is covered); verified by launching `streamlit run app.py` and running an AAPL backtest.

## Deviations

- Backend selector lists Jev but it is not implemented until Phase H; selecting it warns and runs RandomForest. Keeps the UI contract (UI-02) satisfied without a fake backend.

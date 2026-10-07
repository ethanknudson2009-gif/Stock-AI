# Stock-AI — STATE

**Last updated:** 2026-10-07
**Session:** Project initialization — roadmap approved

---

## Project Reference

**Core value:** A running Alpaca paper-trading bot placing real sandbox orders on daily EOD signals, backed by an honest browser-based backtest explorer (Streamlit) that shows RandomForest vs Jev side-by-side.

**Current focus:** Phase A — SignalBackend Protocol (load-bearing gate; blocks all downstream phases)

**Milestone:** v1 — "paper-trading bot in a browser"
**Timeline target:** 2–4 weeks
**Granularity:** coarse
**Mode:** yolo

---

## Current Position

**Phase:** A — SignalBackend Protocol (not started)
**Plan:** none yet
**Status:** Ready for `/gsd:plan-phase A`
**Progress:** `[________] 0/8 phases complete`

---

## Performance Metrics

| Metric | Value |
|---|---|
| v1 REQ-IDs | 42 |
| Phases | 8 |
| Required anti-regression tests | 10 |
| Pre-existing passing tests | 6 |
| HIGH-severity pitfalls to mitigate | 10 (#1–#10) |

---

## Accumulated Context

### Locked Decisions (from PROJECT.md)

- Target: paper-trading bot in 2–4 weeks
- Audience: self + friends/mentors (local-run only)
- Universe: 50+ US liquid equities
- Cadence: daily EOD
- AI model: Jev (TypeSafe AI, 2026) with RandomForest baseline retained
- Broker: Alpaca paper
- UI: Streamlit backtest explorer
- No risk layer in v1 (hard caps only)
- Secrets: `.env` + `python-dotenv` only — NO `st.secrets`

### Load-Bearing Constraints

- **Phase A is the gate.** Nothing downstream starts before `SignalBackend` Protocol ships and all 6 existing tests stay green.
- **Phase H parallelizable with D–G** once A ships.
- **`stock_ai/` must stay Streamlit-free** — one-way flow: `app → stock_ai`, never the reverse.
- **`alpaca-py` imported in exactly one file:** `stock_ai/execution/paper.py`.
- **`typesafe-sdk` pinned to exact minor** (`==1.3.*`) due to documented breaking changes.

### Open Design Questions (resolve during phase planning)

- TimeInForce policy (OPG vs CLS vs DAY) → Phase F
- Pooled vs per-ticker model architecture → Phase D
- Jev model alias confirmation → Phase H

### Todos / Blockers

- None. Ready to proceed to Phase A planning.

---

## Session Continuity

**Next command:** `/gsd:plan-phase A`

**Files on disk:**
- `.planning/PROJECT.md` — locked v1 scope and risk register
- `.planning/REQUIREMENTS.md` — 42 REQ-IDs with phase mapping
- `.planning/ROADMAP.md` — 8-phase build order with success criteria + pitfall mapping + test coverage per phase
- `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS,SUMMARY}.md` — research corpus
- `.planning/config.json` — granularity: coarse, mode: yolo, parallelization: true

**Pre-existing code baseline** (as of 2026-10-06):
- Working CLI: `python main.py backtest --ticker AAPL`
- `stock_ai/` package: `data/`, `features/`, `models/`, `strategy/`, `backtest/`
- 6 passing pytest tests covering critical invariants (no train/test leakage, cost reduces returns, threshold reduces trade frequency)

---

*State for Stock-AI v1 milestone. Initialized 2026-10-07.*

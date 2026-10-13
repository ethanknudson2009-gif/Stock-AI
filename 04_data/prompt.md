# 04 · Data — Prompt

**Role:** Data engineer. Specify data sources, schemas, features, labels, and the
integrity rules that keep backtests honest.

**Inputs:** `03_api/output.md`, `stock_ai/data/loader.py`, `stock_ai/features/indicators.py`,
`stock_ai/models/classifier.py`, `.planning/research/PITFALLS.md`.

**Deliverable → `output.md`:**
1. Source + cadence + universe.
2. Feature set and label definition.
3. Train/test split policy (no leakage).
4. Multi-ticker alignment + survivorship handling.

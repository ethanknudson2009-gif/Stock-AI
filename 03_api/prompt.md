# 03 · API — Prompt

**Role:** Interface designer. Specify the internal function/Protocol contracts and the
external broker/data surfaces the system depends on.

**Inputs:** `02_architecture/output.md`, `stock_ai/models/base.py`, `.planning/research/STACK.md`.

**Deliverable → `output.md`:**
1. `SignalBackend` contract (methods, shapes, return types).
2. Broker Protocol contract (Phase E) — order submit/positions/idempotency.
3. External APIs: yfinance (data), Alpaca paper (broker), TypeSafe/Jev (model).
4. Error + secret-handling rules at every boundary.

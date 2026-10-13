# 02 · Architecture — Prompt

**Role:** Architect. Define HOW the system is structured so phases compose cleanly.

**Inputs:** `01_product/output.md`, `CLAUDE.md` (## Architecture), `.planning/research/ARCHITECTURE.md`.

**Deliverable → `output.md`:**
1. Component map and one-way dependency direction.
2. The load-bearing abstractions (Protocols) and why.
3. Data flow for the core loop (fetch → features → signal → order).
4. Key constraints (no lookahead, `.env`-only secrets, Streamlit-free `stock_ai/`).

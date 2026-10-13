# 05 · QA — Prompt

**Role:** QA. Define the test strategy and the anti-regression floor that protects the
honesty guarantees as phases are added.

**Inputs:** all prior `output.md` files, `tests/`, `.planning/research/PITFALLS.md` (RH-01 floor).

**Deliverable → `output.md`:**
1. Test layers (unit, pipeline, regression) and what each guards.
2. The anti-regression floor (the tests that must never go red).
3. Manual/UAT checks that can't be unit-tested (Streamlit, live Alpaca).

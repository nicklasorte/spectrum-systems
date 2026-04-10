# PLAN — BATCH-AUT-REG-05A-FIX (2026-04-10)

Prompt type: BUILD

## Scope
Repair AUT-05 fixture/command contract for review roadmap generation without weakening validation, then resume governed execution from `AUTONOMY_EXECUTION → BATCH-AUT → AUT-05` and document outcomes.

## Steps
1. Confirm AUT-05 command shape in `slice_registry` and failing fixture contract at `tests/fixtures/roadmaps/aut_reg_05a/review_control_signal.json`.
2. Repair fixture to include `control_decision.system_response` as a non-empty string while preserving existing schema-required metadata.
3. Update `AUT-05` registered command in `contracts/roadmap/slice_registry.json` (if needed) so `build_review_roadmap(...)` receives the control decision envelope expected by runtime validation.
4. Validate AUT-05 in isolation by running the direct `python -c` command and `pytest tests/test_review_roadmap_generator.py -q`.
5. Resume execution from `AUT-05` across `AUT-10` using `roadmap_structure` sequencing + `slice_registry` commands; stop fail-closed on first new failure and capture artifacts/logs.
6. Author `docs/reviews/RVW-BATCH-AUT-REG-05A-FIX.md` and `docs/reviews/BATCH-AUT-REG-05A-FIX-DELIVERY-REPORT.md` with outcomes, progression, and trust verdict.
7. Run any targeted registry/contract tests needed, then commit and open PR with `make_pr`.

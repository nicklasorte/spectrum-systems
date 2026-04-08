# PLAN-BUNDLE-01-EXTENDED-FIX-01-2026-04-08

## Objective
Implement real generated bundle outputs for BUNDLE-01-EXTENDED so the harness review is backed by deterministic runtime artifacts rather than review prose only.

## Scope
- Add a bundle runner script that executes governed checks across PQX, prompt queue, orchestration, failure injection, observability, drift, replay, and budget surfaces.
- Emit required artifacts into a deterministic output directory.
- Add definition-of-done enforcement that fails when review exists without required generated outputs.
- Update the review doc to reference concrete generated artifacts.

## Files planned
1. `scripts/run_harness_integrity_bundle.py` (new)
2. `tests/test_harness_integrity_bundle.py` (new)
3. `docs/reviews/harness_integrity_review.md` (update)

## Non-goals
- No policy weakening.
- No new execution paths outside existing governed module/CLI seams.
- No unrelated refactors.

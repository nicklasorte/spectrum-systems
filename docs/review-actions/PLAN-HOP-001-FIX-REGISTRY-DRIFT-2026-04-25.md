# Plan — HOP-001-FIX-REGISTRY-DRIFT — 2026-04-25

## Prompt type
BUILD

## Roadmap item
HOP-001 follow-up hardening

## Objective
Fix registry drift false schema-missing detection for HOP artifacts and harden 3-letter system enforcement to catch produced-schema gaps earlier.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-HOP-001-FIX-REGISTRY-DRIFT-2026-04-25.md | CREATE | Required plan for multi-file hardening. |
| spectrum_systems/governance/registry_drift_validator.py | MODIFY | Resolve schema lookup bug and tighten registry parsing scope. |
| spectrum_systems/modules/governance/three_letter_system_enforcement.py | MODIFY | Add early produced-schema gate for 3-letter systems. |
| tests/test_3ls_phase1_foundation.py | MODIFY | Regression tests for recursive schema discovery / definitions parsing. |
| tests/test_three_letter_system_enforcement.py | MODIFY | Add early schema-gate regression test in 3LS enforcement audit. |
| docs/reviews/hop_batch1_review.md | MODIFY | Add follow-up finding/fix note for CI drift failure. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_3ls_phase1_foundation.py tests/test_three_letter_system_enforcement.py`
2. `python spectrum_systems/governance/registry_drift_validator.py`
3. `python scripts/run_three_letter_system_enforcement_audit.py --changed-file docs/architecture/system_registry.md`

## Scope exclusions
- No weakening of fail-closed behavior.
- No changes to HOP artifact schema semantics.
- No autonomous optimization behavior.

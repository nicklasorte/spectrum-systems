# Plan — HOP-003A Authority Fix — 2026-04-25

## Prompt type
PLAN

## Roadmap item
HOP-003A-AUTHORITY-FIX

## Objective
Remove authority-shaped naming from newly added HOP-BATCH-3 advisory artifacts so authority leak guard passes without weakening any guard.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-HOP-003A-AUTHORITY-FIX-2026-04-25.md | CREATE | Required multi-file plan for BUILD fix pass. |
| contracts/schemas/hop/harness_routing_decision.schema.json | DELETE | Remove authority-shaped schema name. |
| contracts/schemas/hop/harness_routing_observation.schema.json | CREATE | Non-authoritative replacement schema. |
| contracts/schemas/hop/harness_trial_report.schema.json | DELETE | Remove authority-shaped trial naming if flagged. |
| contracts/schemas/hop/harness_trial_summary.schema.json | CREATE | Advisory naming replacement schema. |
| spectrum_systems/modules/hop/patterns/domain_router.py | MODIFY | Emit routing observation artifact/type/ref + non-authoritative fields. |
| spectrum_systems/modules/hop/trial_runner.py | MODIFY | Emit trial summary artifact/type/ref + non-authoritative fields. |
| spectrum_systems/modules/hop/schemas.py | MODIFY | Register renamed schema artifact types. |
| spectrum_systems/modules/hop/experience_store.py | MODIFY | Update store/index keys for renamed artifact types. |
| tests/hop/test_patterns.py | MODIFY | Validate renamed routing observation artifact. |
| tests/hop/test_trial_runner.py | MODIFY | Validate renamed trial summary artifact and field names. |
| docs/reviews/hop_batch3_review.md | MODIFY | Align naming to advisory-only semantics. |

## Contracts touched
HOP-local schemas in `contracts/schemas/hop/` only.

## Tests that must pass after execution
1. `python scripts/run_authority_leak_guard.py --base-ref ee8446d0cb2ecef7e174582ee0c9538bea32a3f2 --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
2. `python scripts/run_system_registry_guard.py --base-ref ee8446d0cb2ecef7e174582ee0c9538bea32a3f2 --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`
3. `python -m pytest tests/hop -q`

## Scope exclusions
- Do not weaken or modify any guard scripts.
- Do not change non-HOP modules.
- Do not introduce promotion/certification/authority semantics.

## Dependencies
- HOP-003 baseline implementation commit `23a1df3`.

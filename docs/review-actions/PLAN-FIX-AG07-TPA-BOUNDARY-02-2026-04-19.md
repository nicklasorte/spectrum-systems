# Plan — FIX-AG07-TPA-BOUNDARY-02 — 2026-04-19

## Prompt type
PLAN

## Roadmap item
FIX-AG07-TPA-BOUNDARY-02

## Objective
Shrink this branch diff to the AG-07 + TPA governed Python ownership boundary by reverting unrelated governance phase files that are causing SHADOW_OWNERSHIP_OVERLAP.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| contracts/governance/cross-repo-scan-policy.json | REVERT | Outside AG-07 + TPA Python slice |
| contracts/governance/downstream-consent-registry.json | REVERT | Outside AG-07 + TPA Python slice |
| contracts/governance/enforcement-activation-record.json | REVERT | Outside AG-07 + TPA Python slice |
| contracts/governance/schema-registry-manifest.json | REVERT | Outside AG-07 + TPA Python slice |
| contracts/governance/violation-response-policy.json | REVERT | Outside AG-07 + TPA Python slice |
| docs/phase-16-implementation-plan.md | REVERT | Unrelated roadmap artifact |
| docs/phase-16-migration-guide.md | REVERT | Unrelated roadmap artifact |
| ecosystem/spectrum-systems.file-types.schema.json | REVERT | Unrelated schema surface expansion |
| ecosystem/system-registry.json | REVERT | Unrelated ownership expansion |
| ecosystem/system-registry.schema.json | REVERT | Unrelated ownership expansion |
| scripts/validate-governance-boundary.py | REVERT | Unrelated validation surface |
| tests/test_governance_boundary_enforcement.py | REVERT | Unrelated test surface |
| docs/review-actions/PLAN-FIX-AG07-TPA-BOUNDARY-02-2026-04-19.md | CREATE | Required plan-first artifact for multi-file boundary fix |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/run_system_registry_guard.py`
2. `pytest tests/test_failure_eval_generation.py tests/test_generated_eval_registry_change_surface_vocabulary.py tests/test_tpa_contract_sync_preflight.py`

## Scope exclusions
- Do not modify AG-07 or TPA schema semantics.
- Do not alter enforcement guard behavior or add exceptions.
- Do not widen ownership in system registry artifacts.

## Dependencies
- None.

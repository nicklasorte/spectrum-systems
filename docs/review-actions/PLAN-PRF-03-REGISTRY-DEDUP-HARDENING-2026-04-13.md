# Plan — PRF-03-REGISTRY-DEDUP-HARDENING — 2026-04-13

## Prompt type
PLAN

## Roadmap item
PRF-03 regression hardening (registry artifact integrity)

## Objective
Fix duplicate `downstream_consumers` emission in `system_registry_artifact` and add a deterministic, fail-closed registry build/validation path that blocks recurrence.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| contracts/examples/system_registry_artifact.json | MODIFY | Remove duplicate downstream consumers and align canonical ownership artifacts. |
| scripts/build_system_registry_artifact.py | CREATE | Deterministic registry normalization + schema/invariant validation build tool. |
| spectrum_systems/modules/runtime/system_registry_enforcer.py | MODIFY | Preserve strict runtime fail-closed behavior with precise malformed-registry diagnostics. |
| tests/test_system_registry_boundaries.py | MODIFY | Add builder output and dedup regression checks. |
| tests/test_system_registry_boundary_enforcement.py | MODIFY | Add malformed-registry precise error surfacing checks. |
| tests/test_system_handoff_integrity.py | MODIFY | Ensure enforcement remains strict after hardening. |

## Contracts touched
No schema weakening; only enforce existing `system_registry_artifact` uniqueness semantics and add build-time validation.

## Tests that must pass after execution
1. `pytest tests/test_system_registry_boundaries.py -q`
2. `pytest tests/test_system_registry_boundary_enforcement.py -q`
3. `pytest tests/test_system_handoff_integrity.py -q`
4. `pytest tests/test_top_level_conductor.py -q`
5. `pytest tests/test_tlc_handoff_flow.py -q`
6. `pytest tests/test_tlc_requires_admission_for_repo_write.py -q`
7. `pytest tests/test_github_closure_continuation.py -q`
8. `pytest tests/test_roadmap_execution.py -q`
9. `pytest tests/test_roadmap_draft_and_approval.py -q`
10. `pytest tests/test_pre_pr_repair_loop.py -q`
11. `pytest tests/test_failure_learning_artifacts.py -q`
12. `pytest`

## Scope exclusions
- No schema weakening (`uniqueItems` remains intact).
- No silent runtime repair in enforcer load path.
- No unrelated architecture refactors.

## Dependencies
- Existing schema `contracts/schemas/system_registry_artifact.schema.json` and strict runtime validation path.

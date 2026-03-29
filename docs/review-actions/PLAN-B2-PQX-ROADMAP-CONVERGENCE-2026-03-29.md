# Plan — B2 PQX Roadmap Convergence + Legacy-Compatible Authority Bridge — 2026-03-29

## Prompt type
PLAN

## Roadmap item
B2 — PQX Roadmap Convergence + Legacy-Compatible Authority Bridge

## Objective
Establish a single deterministic roadmap authority-resolution path for PQX consumers that recognizes `docs/roadmaps/system_roadmap.md` as active authority while preserving `docs/roadmap/system_roadmap.md` as the machine-executable compatibility surface with fail-closed alignment checks.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-B2-PQX-ROADMAP-CONVERGENCE-2026-03-29.md | CREATE | Required PLAN artifact before multi-file BUILD/WIRE changes. |
| docs/review-actions/B2_EXECUTION_SUMMARY_2026-03-29.md | CREATE | Required execution summary artifact for this slice. |
| docs/roadmaps/roadmap_authority.md | MODIFY | Make authority resolution and compatibility bridge semantics explicit and testable. |
| docs/roadmaps/system_roadmap.md | MODIFY | Add explicit bridge metadata consumed by deterministic authority checks. |
| docs/roadmaps/pqx_authority_bridge.md | CREATE | Narrow bridge design note and cutover plan (if needed for clarity). |
| docs/roadmap/system_roadmap.md | MODIFY | Preserve legacy machine-readable contract and add explicit compatibility metadata. |
| docs/roadmap/roadmap_step_contract.md | MODIFY | Clarify step-contract anchoring under bridged authority model. |
| docs/roadmap/pqx_execution_map.md | MODIFY | Document authoritative source selection behavior for PQX map consumers. |
| spectrum_systems/modules/pqx_backbone.py | MODIFY | Add deterministic authority resolution + compatibility checks and keep parser semantics stable. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Preserve sequence-runner compatibility with explicit roadmap authority metadata (narrow, non-architectural). |
| tests/test_pqx_backbone.py | MODIFY | Add bridge authority resolution, compatibility, and fail-closed tests. |
| tests/test_pqx_sequence_runner.py | MODIFY | Add regression check ensuring sequence runner behavior remains compatible. |
| tests/test_roadmap_authority.py | MODIFY | Add deterministic checks for active/subordinate authority declarations. |
| tests/test_roadmap_step_contract.py | MODIFY | Verify step-contract anchoring is preserved under bridge semantics. |
| tests/test_roadmap_tracker.py | MODIFY | Tight compatibility assertion ensuring no conflicting authority assumptions leak into tracker surface. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_pqx_backbone.py`
2. `pytest tests/test_pqx_sequence_runner.py`
3. `pytest tests/test_roadmap_authority.py`
4. `pytest tests/test_roadmap_step_contract.py`
5. `pytest tests/test_roadmap_tracker.py`
6. `pytest tests/test_contracts.py`
7. `pytest tests/test_module_architecture.py`
8. `pytest`
9. `PLAN_FILES='docs/review-actions/PLAN-B2-PQX-ROADMAP-CONVERGENCE-2026-03-29.md docs/review-actions/B2_EXECUTION_SUMMARY_2026-03-29.md docs/roadmaps/system_roadmap.md docs/roadmaps/roadmap_authority.md docs/roadmap/system_roadmap.md docs/roadmap/roadmap_step_contract.md docs/roadmap/pqx_execution_map.md spectrum_systems/modules/pqx_backbone.py spectrum_systems/modules/pqx_sequence_runner.py tests/test_pqx_backbone.py tests/test_pqx_sequence_runner.py tests/test_roadmap_authority.py tests/test_roadmap_step_contract.py tests/test_roadmap_tracker.py' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign PQX architecture or introduce a second parser semantics path.
- Do not change contract schemas unrelated to roadmap authority bridging.
- Do not implement full N-slice orchestration in this slice.
- Do not remove legacy roadmap compatibility requirements.

## Dependencies
- B1 roadmap authority consolidation and execution-state inventory artifacts must remain intact.

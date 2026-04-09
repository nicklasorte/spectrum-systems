# Plan — BATCH-AEX-FIX-03 — 2026-04-09

Primary prompt type: BUILD

## Scope
Enforce mandatory repo-write lineage at the PQX execution boundary so no repo-write-capable or unknown-intent execution can bypass AEX/TLC lineage validation.

## Files expected to change
| File | Action | Why |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-AEX-FIX-03-2026-04-09.md | CREATE | Plan-first requirement for >2 file BUILD change set. |
| PLANS.md | MODIFY | Register active plan entry. |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Add authoritative boundary guard for execution intent + repo-write lineage enforcement. |
| scripts/pqx_runner.py | MODIFY | Ensure direct CLI caller declares execution intent and forwards lineage artifacts. |
| spectrum_systems/modules/pqx_backbone.py | MODIFY | Ensure direct caller explicitly declares non-repo-write intent. |
| spectrum_systems/modules/runtime/codex_to_pqx_task_wrapper.py | MODIFY | Ensure wrapped non-mutating path explicitly declares non-repo-write intent. |
| spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py | MODIFY | Ensure direct caller path explicitly declares non-repo-write intent. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Ensure direct default execution path explicitly declares non-repo-write intent. |
| spectrum_systems/orchestration/pqx_handoff_adapter.py | MODIFY | Route repo-write lineage/intent through boundary guard. |
| tests/test_aex_repo_write_boundary_structural.py | MODIFY | Tighten structural rule semantics to boundary-enforcement invariant. |
| tests/test_pqx_slice_runner.py | MODIFY | Add direct-boundary invariant tests for repo_write/unknown intent. |
| tests/test_pqx_handoff_adapter.py | MODIFY | Add public caller invariant assertion for fail-closed repo-write without lineage at boundary. |

## Invariants to preserve
1. Artifact-first execution remains intact.
2. Fail-closed behavior is mandatory for unknown or invalid repo-write lineage.
3. AEX admission artifacts and TLC handoff remain the single source of truth for repo-write lineage.
4. Existing TLC/cycle runner protections continue to pass.

## Validation plan
- Run focused tests for boundary and caller paths.
- Run preserved guardrail tests called out in the batch objective.

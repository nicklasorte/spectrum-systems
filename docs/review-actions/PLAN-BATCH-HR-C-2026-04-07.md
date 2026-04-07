# Plan — BATCH-HR-C — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-HR-C (HR-04B + HR-05 + HR-06 + HR-07)

## Objective
Implement fail-closed pre-PR governance closure, canonical human checkpoint and permission decision artifact contracts, and a consolidated runtime permission decision path with thin integration seams.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-HR-C-2026-04-07.md | CREATE | Required plan record before multi-file/schema work. |
| PLANS.md | MODIFY | Register this plan in active-plan index. |
| spectrum_systems/modules/runtime/pre_pr_governance_closure.py | CREATE | Local pre-PR closure loop with bounded auto-repair and fail-closed gate decision. |
| spectrum_systems/modules/runtime/permission_governance.py | CREATE | Canonical permission evaluation/decision emission and human-checkpoint linkage path. |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY | Integrate pre-PR closure gate before merge-ready terminal transition in repair loop seam. |
| spectrum_systems/modules/runtime/codex_to_pqx_task_wrapper.py | MODIFY | Route governed execution permission checks through canonical permission path. |
| scripts/run_contract_preflight.py | MODIFY | Add deterministic required-surface repair registration helper used by pre-PR closure path. |
| contracts/schemas/human_checkpoint_request.schema.json | CREATE | Canonical human checkpoint request artifact schema. |
| contracts/schemas/human_checkpoint_decision.schema.json | CREATE | Canonical human checkpoint decision artifact schema. |
| contracts/schemas/approval_boundary_record.schema.json | CREATE | Canonical approval boundary record artifact schema. |
| contracts/schemas/permission_decision_record.schema.json | CREATE | Canonical permission decision artifact schema. |
| contracts/schemas/permission_request_record.schema.json | CREATE | Canonical permission request artifact schema. |
| contracts/examples/human_checkpoint_request.json | CREATE | Golden-path example. |
| contracts/examples/human_checkpoint_decision.json | CREATE | Golden-path example. |
| contracts/examples/approval_boundary_record.json | CREATE | Golden-path example. |
| contracts/examples/permission_request_record.json | CREATE | Golden-path example. |
| contracts/examples/permission_decision_record.json | CREATE | Golden-path example. |
| contracts/standards-manifest.json | MODIFY | Register new artifact contracts and versions. |
| tests/test_pre_pr_governance_closure.py | CREATE | Focused tests for pre-PR closure/block/repair loop behavior. |
| tests/test_permission_governance.py | CREATE | Focused tests for permission decision and human-checkpoint seams. |
| tests/test_contracts.py | MODIFY | Validate new contract examples. |
| tests/test_codex_to_pqx_task_wrapper.py | MODIFY | Ensure wrapper path uses consolidated permission decision seam. |
| docs/architecture/control_surfaces_and_pre_pr_governance.md | CREATE | Architecture doc for HR-C control-surface closure. |
| docs/architecture/system_registry.md | MODIFY | Update authoritative 3-letter system boundaries with HNX role. |

## Contracts touched
- New schemas: `human_checkpoint_request`, `human_checkpoint_decision`, `approval_boundary_record`, `permission_decision_record`, `permission_request_record`.
- Manifest update: `contracts/standards-manifest.json` entries for the above artifact types.

## Tests that must pass after execution
1. `pytest tests/test_pre_pr_governance_closure.py tests/test_permission_governance.py tests/test_codex_to_pqx_task_wrapper.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/run_contract_preflight.py --changed-path contracts/schemas/permission_decision_record.schema.json --changed-path spectrum_systems/modules/runtime/permission_governance.py --changed-path spectrum_systems/modules/runtime/pre_pr_governance_closure.py`

## Scope exclusions
- Do not redesign CI workflows.
- Do not introduce a second permission engine or review system.
- Do not weaken existing strategy/control/promotion gates.
- Do not add free-text-only approval flows.

## Dependencies
- HR-A and HR-B stage-contract/time semantics are already complete and treated as immutable authority surfaces.

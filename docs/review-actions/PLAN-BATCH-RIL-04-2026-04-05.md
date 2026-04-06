# Plan — BATCH-RIL-04 — 2026-04-05

## Prompt type
PLAN

## Roadmap item
BATCH-RIL-04 (RIL-004)

## Objective
Implement a deterministic, fail-closed, read-only projection adapter that consumes `review_integration_packet_artifact` and emits schema-backed roadmap/control-loop/readiness projection artifacts plus a top-level bundle artifact.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-RIL-04-2026-04-05.md | CREATE | Record required PLAN prior to multi-file BUILD scope. |
| spectrum_systems/modules/runtime/review_projection_adapter.py | CREATE | Add RIL-004 read-only projection adapter implementation. |
| contracts/schemas/review_projection_bundle_artifact.schema.json | CREATE | Define governed contract for top-level projection bundle. |
| contracts/schemas/roadmap_review_projection_artifact.schema.json | CREATE | Define governed contract for roadmap read-only projection. |
| contracts/schemas/control_loop_review_intake_artifact.schema.json | CREATE | Define governed contract for control-loop read-only intake projection. |
| contracts/schemas/readiness_review_projection_artifact.schema.json | CREATE | Define governed contract for readiness read-only aggregate projection. |
| contracts/examples/review_projection_bundle_artifact.json | CREATE | Golden-path example for projection bundle contract. |
| contracts/examples/roadmap_review_projection_artifact.json | CREATE | Golden-path example for roadmap projection contract. |
| contracts/examples/control_loop_review_intake_artifact.json | CREATE | Golden-path example for control-loop intake projection contract. |
| contracts/examples/readiness_review_projection_artifact.json | CREATE | Golden-path example for readiness projection contract. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and version bump for publication. |
| tests/test_review_projection_adapter.py | CREATE | Deterministic/fail-closed/provenance tests for RIL-004 adapter. |

## Contracts touched
- `contracts/schemas/review_projection_bundle_artifact.schema.json` (new)
- `contracts/schemas/roadmap_review_projection_artifact.schema.json` (new)
- `contracts/schemas/control_loop_review_intake_artifact.schema.json` (new)
- `contracts/schemas/readiness_review_projection_artifact.schema.json` (new)
- `contracts/standards-manifest.json` (version bump + contract registrations)

## Tests that must pass after execution
1. `pytest tests/test_review_projection_adapter.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify RIL-001, RIL-002, or RIL-003 parsing/classification/routing logic.
- Do not add enforcement, policy mutation, or reprioritization behavior.
- Do not consume raw review markdown/action-tracker markdown in RIL-004.
- Do not introduce new repositories, modules outside `spectrum_systems/modules/runtime`, or unrelated refactors.

## Dependencies
- RIL-003 (`review_integration_packet_artifact`) must be available and schema-valid.

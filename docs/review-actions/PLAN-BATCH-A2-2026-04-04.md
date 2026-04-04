# Plan — BATCH-A2 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-A2 — Capability Readiness + Trust Posture

## Objective
Add a deterministic, fail-closed capability-readiness layer that emits a governed readiness artifact each cycle and constrains unattended operation based on evidence-backed trust posture.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-A2-2026-04-04.md | CREATE | Record PLAN-first scope, contract, and validation commitments for BATCH-A2. |
| PLANS.md | MODIFY | Register BATCH-A2 as an active plan. |
| contracts/schemas/capability_readiness_record.schema.json | CREATE | Contract-first schema for governed readiness artifact. |
| contracts/examples/capability_readiness_record.json | CREATE | Golden-path example for readiness artifact validation. |
| contracts/schemas/build_summary.schema.json | MODIFY | Surface readiness state and references in operator summary schema. |
| contracts/examples/build_summary.json | MODIFY | Keep golden example aligned with readiness schema additions/version bump. |
| contracts/schemas/batch_handoff_bundle.schema.json | MODIFY | Carry readiness state/reference in bounded batch handoff memory. |
| contracts/examples/batch_handoff_bundle.json | MODIFY | Keep handoff example aligned with readiness schema additions/version bump. |
| contracts/standards-manifest.json | MODIFY | Register capability_readiness_record and bump touched contract versions. |
| spectrum_systems/modules/runtime/capability_readiness.py | CREATE | Implement deterministic evaluate_capability_readiness(...) fail-closed logic. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Integrate readiness evaluation/emission and wire readiness state into autonomy decisions + output artifacts. |
| tests/test_system_cycle_operator.py | MODIFY | Add readiness-state, propagation, determinism, and fail-closed coverage. |
| tests/test_roadmap_multi_batch_executor.py | MODIFY | Add readiness-adjacent derivation/integration assertions at batch seam. |
| tests/test_contracts.py | MODIFY | Include capability_readiness_record in contract example validation set. |
| tests/test_contract_enforcement.py | MODIFY | Enforce standards-manifest registration and version expectations for readiness integration. |

## Contracts touched
- Create: `capability_readiness_record` (v1.0.0)
- Update: `build_summary` (version bump, additive readiness fields)
- Update: `batch_handoff_bundle` (version bump, additive readiness fields)
- Update: `contracts/standards-manifest.json` (register new contract + bumped versions)

## Tests that must pass after execution
1. `pytest tests/test_system_cycle_operator.py`
2. `pytest tests/test_roadmap_multi_batch_executor.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_contract_enforcement.py`
5. `python scripts/run_contract_enforcement.py`
6. `pytest`
7. `PLAN_FILES="docs/review-actions/PLAN-BATCH-A2-2026-04-04.md PLANS.md contracts/schemas/capability_readiness_record.schema.json contracts/examples/capability_readiness_record.json contracts/schemas/build_summary.schema.json contracts/examples/build_summary.json contracts/schemas/batch_handoff_bundle.schema.json contracts/examples/batch_handoff_bundle.json contracts/standards-manifest.json spectrum_systems/modules/runtime/capability_readiness.py spectrum_systems/modules/runtime/system_cycle_operator.py tests/test_system_cycle_operator.py tests/test_roadmap_multi_batch_executor.py tests/test_contracts.py tests/test_contract_enforcement.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign roadmap/control-loop/autonomy guardrail semantics outside readiness gating.
- Do not introduce model-driven control logic or hidden mutable state.
- Do not refactor unrelated modules, contracts, or tests.

## Dependencies
- BATCH-A1 autonomy guardrail outputs remain authoritative and are consumed as input signals.
- Existing exception-routing and bounded execution artifacts remain unchanged in semantic ownership.

# Plan — BATCH-CDE-01 — 2026-04-06

## Prompt type
PLAN

## Roadmap item
BATCH-CDE-01 / CDE-001 — Closure Decision Engine

## Objective
Implement a deterministic Closure Decision Engine that consumes governed review/closure artifacts and emits a schema-valid `closure_decision_artifact` (plus optional deterministic `next_step_prompt_artifact`) with traceable evidence-backed closure outcomes.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-CDE-01-2026-04-06.md | CREATE | Required plan-first artifact before multi-file BUILD work. |
| spectrum_systems/modules/runtime/closure_decision_engine.py | CREATE | Deterministic CDE runtime module implementing bounded closure decision rules. |
| contracts/schemas/closure_decision_artifact.schema.json | CREATE | Canonical contract for closure decision output artifact. |
| contracts/examples/closure_decision_artifact.json | CREATE | Golden-path example for closure decision artifact. |
| contracts/schemas/next_step_prompt_artifact.schema.json | CREATE | Optional bounded structured next-step prompt metadata contract. |
| contracts/examples/next_step_prompt_artifact.json | CREATE | Golden-path example for optional next-step prompt artifact. |
| contracts/standards-manifest.json | MODIFY | Register new artifact contracts and bump manifest version. |
| tests/test_closure_decision_engine.py | CREATE | Deterministic test coverage for CDE rules, replay, traceability, and optional prompt artifact generation. |
| docs/runtime/closure_decision_engine.md | CREATE | Role-boundary documentation clarifying CDE scope and TLC-consumer boundary. |

## Contracts touched
- `contracts/schemas/closure_decision_artifact.schema.json` (new)
- `contracts/schemas/next_step_prompt_artifact.schema.json` (new)
- `contracts/standards-manifest.json` version bump and contract registrations

## Tests that must pass after execution
1. `pytest tests/test_closure_decision_engine.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add orchestration/execution logic (TLC/PQX/FRE/SEL/PRG behavior).
- Do not modify unrelated runtime modules, schemas, or tests.
- Do not introduce policy-mutation or bypass authorization logic.

## Dependencies
- Existing governed review artifacts/contracts (`review_artifact`, `review_signal_artifact`, `review_control_signal_artifact`, `review_integration_packet_artifact`, `review_projection_bundle_artifact`, `review_consumer_output_bundle_artifact`) must remain authoritative inputs.

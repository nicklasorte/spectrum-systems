# Plan — BATCH-HR-B — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-HR-B — HR-03 + HR-04

## Objective
Unify long-running checkpoint/resume/async-wait/reset-handoff semantics under HNX with canonical contracts, deterministic runtime policy evaluation, and one enforced execution seam.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-HR-B-2026-04-07.md | CREATE | Required plan artifact before multi-file BUILD scope. |
| contracts/schemas/stage_contract.schema.json | MODIFY | Add canonical long-running execution policy fields. |
| contracts/schemas/checkpoint_record.schema.json | CREATE | Canonical HNX checkpoint artifact schema. |
| contracts/schemas/resume_record.schema.json | CREATE | Canonical HNX resume attempt artifact schema. |
| contracts/schemas/async_wait_record.schema.json | CREATE | Canonical HNX async wait artifact schema. |
| contracts/schemas/handoff_artifact.schema.json | CREATE | Canonical HNX governed handoff artifact schema. |
| contracts/examples/stage_contracts/pqx_stage_contract.json | MODIFY | Add new required long-running policy fields for schema conformance. |
| contracts/examples/stage_contracts/prompt_queue_stage_contract.json | MODIFY | Add new required long-running policy fields for schema conformance. |
| contracts/standards-manifest.json | MODIFY | Register new canonical contracts and bump standards version metadata. |
| contracts/examples/checkpoint_record.json | CREATE | Golden-path example for new checkpoint_record contract registration. |
| contracts/examples/resume_record.json | CREATE | Golden-path example for new resume_record contract registration. |
| contracts/examples/async_wait_record.json | CREATE | Golden-path example for new async_wait_record contract registration. |
| contracts/examples/handoff_artifact.json | CREATE | Golden-path example for new handoff_artifact contract registration. |
| spectrum_systems/modules/runtime/hnx_execution_state.py | CREATE | Deterministic HNX continuity runtime functions. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Enforce HNX long-running policy and continuity validation at real transition seam. |
| tests/test_stage_contract_runtime.py | MODIFY | Cover new stage-contract policy fields and continuity policy behavior. |
| tests/test_sequence_transition_policy.py | MODIFY | Verify seam fail-closed continuity enforcement. |
| tests/test_hnx_execution_state.py | CREATE | Unit tests for deterministic HNX checkpoint/resume/wait/handoff runtime layer. |
| tests/test_contracts.py | MODIFY | Add coverage for new HNX continuity contract examples. |
| docs/architecture/hnx_long_running_execution.md | CREATE | Architecture documentation for canonical HNX continuity spine. |
| docs/review-actions/HR-B-action-note-2026-04-07.md | CREATE | Concise review/action note for alignment and migration discipline. |

## Contracts touched
- stage_contract (schema additive update)
- checkpoint_record (new)
- resume_record (new)
- async_wait_record (new)
- handoff_artifact (new)
- standards-manifest version metadata and contract entries

## Tests that must pass after execution
1. `pytest tests/test_hnx_execution_state.py tests/test_stage_contract_runtime.py tests/test_sequence_transition_policy.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/run_contract_preflight.py --help`

## Scope exclusions
- Do not migrate all existing continuity artifacts; only align one real seam.
- Do not introduce a second control loop, queue abstraction, or promotion model.
- Do not alter unrelated module boundaries or refactor unrelated runtime modules.

## Dependencies
- HR-A stage contract seam must remain authoritative and intact.
- Existing PQX/prompt-queue control/eval/promotion gates remain mandatory.

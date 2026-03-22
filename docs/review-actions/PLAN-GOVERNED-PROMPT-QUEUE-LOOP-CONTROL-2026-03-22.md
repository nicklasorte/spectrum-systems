# Plan — GOVERNED PROMPT QUEUE LOOP CONTROL — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Governed Prompt Queue — deterministic repair loop control / budget enforcement slice

## Objective
Add contract-first loop control and bounded generation enforcement so repair re-entry is deterministic, lineage-validated, and fail-closed.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/prompt_queue_loop_control_decision.schema.json | CREATE | Canonical contract for loop control decisions |
| contracts/examples/prompt_queue_loop_control_decision.json | CREATE | Golden-path example for loop control decision |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump contract publication version |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add `generation_count` to governed work item schema |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Mirror `generation_count` requirement in queue state embedded work item |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Keep canonical example schema-valid with generation tracking |
| contracts/examples/prompt_queue_state.json | MODIFY | Keep canonical queue example schema-valid with generation tracking |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add generation_count model field and deterministic initialization |
| spectrum_systems/modules/prompt_queue/repair_child_creator.py | MODIFY | Enforce parent-child monotonic generation_count derivation |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Allow deterministic blocked terminal transition from executed_failure when loop budget exceeded |
| spectrum_systems/modules/prompt_queue/loop_control_policy.py | CREATE | Pure logic for lineage checks + bounded loop control decision |
| spectrum_systems/modules/prompt_queue/loop_control_artifact_io.py | CREATE | Schema validation + deterministic artifact write |
| spectrum_systems/modules/prompt_queue/loop_control_queue_integration.py | CREATE | Deterministic queue mutation + fail-closed transition guard |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export loop-control module API |
| scripts/run_prompt_queue_loop_control.py | CREATE | Thin CLI wiring load→evaluate→write→integrate |
| tests/test_prompt_queue_loop_control.py | CREATE | Deterministic tests for policy, failure, and integration safety |
| docs/reviews/governed_prompt_queue_loop_control_report.md | CREATE | Required delivery report artifact |
| PLANS.md | MODIFY | Register newly created plan in active plans table |

## Contracts touched
- New: `prompt_queue_loop_control_decision` (schema version `1.0.0`)
- Modified: `prompt_queue_work_item` and `prompt_queue_state` to include `generation_count`
- Modified: `contracts/standards-manifest.json` version publication bump + contract registration

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_loop_control.py`
2. `pytest tests/test_prompt_queue_repair_child_creation.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/contract-boundary-audit/run.sh`

## Scope exclusions
- Do not add retry scheduling or provider execution behavior
- Do not implement multi-item coordination logic
- Do not refactor unrelated prompt queue orchestration modules
- Do not alter artifact envelope or provenance shared contracts

## Dependencies
- Existing governed prompt queue MVP and repair-child creation slice must remain intact
- Existing prompt queue state machine transitions must remain authoritative

# Plan — BATCH-PRG-ENFORCE — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-PRG-ENFORCE

## Objective
Turn program-layer artifacts into deterministic enforcement boundaries for roadmap validation, batch continuation, drift detection, and operator-facing stop/continue outputs.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-PRG-ENFORCE-2026-04-04.md | CREATE | Required plan-first artifact for this multi-file build. |
| PLANS.md | MODIFY | Register this plan in active plans table. |
| contracts/schemas/program_constraint_signal.schema.json | CREATE | Define governed contract for deterministic program constraint emission. |
| contracts/schemas/program_roadmap_alignment_result.schema.json | CREATE | Define governed contract for roadmap-program alignment validation output. |
| contracts/schemas/program_drift_signal.schema.json | CREATE | Define governed contract for program drift detection output. |
| contracts/schemas/program_feedback_record.schema.json | CREATE | Define governed contract for roadmap feedback loop to future generation. |
| contracts/examples/program_constraint_signal.json | CREATE | Golden-path example for contract validation. |
| contracts/examples/program_roadmap_alignment_result.json | CREATE | Golden-path example for contract validation. |
| contracts/examples/program_drift_signal.json | CREATE | Golden-path example for contract validation. |
| contracts/examples/program_feedback_record.json | CREATE | Golden-path example for contract validation. |
| contracts/standards-manifest.json | MODIFY | Publish new contract versions and registry pins. |
| spectrum_systems/modules/runtime/program_layer.py | MODIFY | Implement deterministic program constraint, alignment, drift, and feedback builders. |
| spectrum_systems/modules/runtime/roadmap_selector.py | MODIFY | Add deterministic roadmap alignment validation surface against program constraints. |
| spectrum_systems/modules/runtime/roadmap_multi_batch_executor.py | MODIFY | Enforce program constraints at continuation and pre-batch execution gates with explicit reason codes. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Surface program alignment/drift/constraint-caused continuation state in operator artifacts. |
| tests/test_program_layer.py | MODIFY | Add deterministic unit coverage for new program-layer governance artifacts. |
| tests/test_roadmap_selector.py | MODIFY | Add alignment validation tests and fail-closed block behavior. |
| tests/test_roadmap_multi_batch_executor.py | MODIFY | Add program-caused stop/freeze/continuation behavior tests. |
| tests/test_system_cycle_operator.py | MODIFY | Add operator visibility checks for program-caused stop/continue state. |
| tests/test_contracts.py | MODIFY | Validate new contracts/examples in contract test surface. |

## Contracts touched
- program_constraint_signal (new)
- program_roadmap_alignment_result (new)
- program_drift_signal (new)
- program_feedback_record (new)
- contracts/standards-manifest.json (version bump + new contract pins)

## Tests that must pass after execution
1. `pytest tests/test_system_cycle_operator.py`
2. `pytest tests/test_roadmap_selector.py`
3. `pytest tests/test_roadmap_multi_batch_executor.py`
4. `pytest tests/test_control_loop.py`
5. `pytest tests/test_contracts.py`
6. `pytest tests/test_contract_enforcement.py`
7. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not redesign PQX orchestration architecture.
- Do not change allow/warn/freeze/block semantic vocabulary.
- Do not modify unrelated modules or non-program governance contracts.

## Dependencies
- Existing BATCH-M/BATCH-RDX loop and operator artifacts must remain authoritative execution surfaces.

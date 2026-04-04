# Plan — BATCH-A3 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-A3 — Exception Router

## Objective
Add deterministic exception classification and governed resolution routing artifacts that map failure states to explicit next actions and propagate those outputs through cycle, handoff, and operator surfaces.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-A3-2026-04-04.md | CREATE | Required plan-first artifact for this multi-file contract/runtime/test change. |
| PLANS.md | MODIFY | Register this active plan in the plan index. |
| contracts/schemas/exception_classification_record.schema.json | CREATE | New governed contract for deterministic exception classification output. |
| contracts/schemas/exception_resolution_record.schema.json | CREATE | New governed contract for deterministic exception routing output. |
| contracts/examples/exception_classification_record.json | CREATE | Golden-path example for exception classification contract validation. |
| contracts/examples/exception_resolution_record.json | CREATE | Golden-path example for exception resolution contract validation. |
| contracts/examples/build_summary.json | MODIFY | Keep golden example aligned with new exception-routing operator summary fields. |
| contracts/schemas/batch_handoff_bundle.schema.json | MODIFY | Add required exception routing propagation fields. |
| contracts/schemas/build_summary.schema.json | MODIFY | Surface exception class and resolution recommendation in operator summary. |
| contracts/schemas/next_cycle_input_bundle.schema.json | MODIFY | Carry latest exception routing outputs into next-cycle machine input. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and bump manifest metadata/version. |
| spectrum_systems/modules/runtime/exception_router.py | CREATE | Implement deterministic classification + routing logic. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Integrate exception router outputs into governed cycle artifacts. |
| tests/test_system_cycle_operator.py | MODIFY | Validate routing propagation and operator/handoff integration behaviors. |
| tests/test_next_governed_cycle_runner.py | MODIFY | Validate next-cycle bundle compatibility with routed exception fields. |
| tests/test_contracts.py | MODIFY | Add contract example validation coverage for new routing contracts. |
| tests/test_contract_enforcement.py | MODIFY | Add enforcement-level contract coverage for new routing contracts. |
| tests/test_exception_router.py | CREATE | Determinism and mapping/fail-closed coverage for classification/routing logic. |

## Contracts touched
- New: `exception_classification_record` (`1.0.0`)
- New: `exception_resolution_record` (`1.0.0`)
- Updated: `batch_handoff_bundle` (schema version bump)
- Updated: `build_summary` (schema version bump)
- Updated: `next_cycle_input_bundle` (schema version bump)
- Updated: `standards_manifest` entry metadata/version

## Tests that must pass after execution
1. `pytest tests/test_system_cycle_operator.py`
2. `pytest tests/test_roadmap_multi_batch_executor.py`
3. `pytest tests/test_next_governed_cycle_runner.py`
4. `pytest tests/test_contracts.py`
5. `pytest tests/test_contract_enforcement.py`
6. `pytest tests/test_exception_router.py`
7. `python scripts/run_contract_enforcement.py`
8. `pytest`
9. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add model-based routing, free-text policy inference, or hidden state.
- Do not auto-create remediation batches beyond existing governed artifact emission.
- Do not alter roadmap selection semantics beyond adding machine-readable exception outputs.
- Do not refactor unrelated runtime modules or contracts.

## Dependencies
- BATCH-A1 autonomy guardrails artifacts/signals available for routing inputs.
- Existing governed cycle artifacts remain source-of-truth for stop and control semantics.

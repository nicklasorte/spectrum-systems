# Plan — BATCH-HR-A-FIX-02 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-HR-A-FIX-02 — Repair artifact_class taxonomy mismatch for stage_contract

## Objective
Promote `governance` to a valid artifact class across authoritative taxonomy validation surfaces so `stage_contract` remains correctly classified without weakening checks.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| tests/test_artifact_classification.py | MODIFY | Expand allowed taxonomy and add explicit governance class expectation coverage. |
| contracts/schemas/artifact_class_registry.schema.json | MODIFY | Extend canonical artifact class schema enum to include `governance`. |
| contracts/artifact-class-registry.json | MODIFY | Register `governance` as canonical class and define deterministic transitions. |
| contracts/schemas/standards_manifest.schema.json | MODIFY | Allow `governance` in standards-manifest contract entries. |
| ecosystem/dependency-graph.schema.json | MODIFY | Allow `governance` class in artifact/contract nodes. |
| docs/artifact-classification-standard.md | MODIFY | Document governance as canonical class in taxonomy standard. |
| docs/artifact-envelope-standard.md | MODIFY | Align envelope class vocabulary with canonical taxonomy. |
| docs/review-actions/PLAN-BATCH-HR-A-FIX-02-2026-04-07.md | CREATE | Required plan artifact for this multi-file fix. |

## Contracts touched
- `contracts/schemas/artifact_class_registry.schema.json`
- `contracts/schemas/standards_manifest.schema.json`

## Tests that must pass after execution
1. `pytest tests/test_artifact_classification.py tests/test_dependency_graph.py`
2. `pytest tests/test_stage_contract_runtime.py tests/test_sequence_transition_policy.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not redesign full artifact model.
- Do not weaken validation gates or remove enum checks.
- Do not reclassify `stage_contract` into a different class.
- Do not touch unrelated runtime/orchestration systems.

## Dependencies
- HR-A stage-contract registration in `contracts/standards-manifest.json` remains unchanged and must validate under updated taxonomy.

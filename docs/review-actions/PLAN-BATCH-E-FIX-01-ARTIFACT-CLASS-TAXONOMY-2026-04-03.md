# Plan — BATCH-E-FIX-01-ARTIFACT-CLASS-TAXONOMY — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-E FIX 01 — Artifact Class Taxonomy Hardening

## Objective
Promote `governance` to a first-class artifact class in all taxonomy validation surfaces so standards manifest and dependency-graph artifacts validate consistently.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-E-FIX-01-ARTIFACT-CLASS-TAXONOMY-2026-04-03.md | CREATE | Required plan artifact for multi-file fix |
| tests/test_artifact_classification.py | MODIFY | Expand allowed artifact classes and add governance assertions |
| ecosystem/dependency-graph.schema.json | MODIFY | Accept governance class in artifact/contract node validation |
| contracts/schemas/standards_manifest.schema.json | MODIFY | Accept governance class in standards-manifest contract_entry enum |
| contracts/schemas/artifact_class_registry.schema.json | MODIFY | Accept governance class in class definitions and transitions |
| contracts/artifact-class-registry.json | MODIFY | Publish governance class and explicit transitions |
| docs/artifact-classification-standard.md | MODIFY | Update canonical taxonomy from 3 to 4 classes |
| scripts/build_dependency_graph.py | MODIFY | Keep taxonomy-consistent inference for governance artifacts |

## Contracts touched
- `contracts/schemas/standards_manifest.schema.json`
- `contracts/schemas/artifact_class_registry.schema.json`

## Tests that must pass after execution
1. `pytest tests/test_artifact_classification.py tests/test_dependency_graph.py`
2. `pytest`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh` (with `PLAN_FILES` set)

## Scope exclusions
- Do not rename artifact classes or remap existing contracts away from governance.
- Do not redesign artifact taxonomy beyond adding governance support.
- Do not modify unrelated runtime/control-loop logic.

## Dependencies
- Existing standards-manifest remains canonical source of artifact contract class declarations.

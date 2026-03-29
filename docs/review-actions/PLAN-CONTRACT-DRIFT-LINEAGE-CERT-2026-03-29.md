# Plan — CONTRACT-DRIFT-LINEAGE-CERT — 2026-03-29

## Prompt type
PLAN

## Roadmap item
Contract drift migration (artifact_lineage + certification builders)

## Objective
Align stale artifact builders/helpers with current canonical contract requirements for artifact_lineage, control_loop_certification_pack, and done_certification_record without loosening validation.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CONTRACT-DRIFT-LINEAGE-CERT-2026-03-29.md | CREATE | Required plan artifact for multi-file contract migration |
| PLANS.md | MODIFY | Register new active plan |
| spectrum_systems/modules/runtime/artifact_lineage.py | MODIFY | Add canonical identity/lineage graph fields in shared lineage builder |
| scripts/run_control_loop_certification.py | MODIFY | Ensure generated certification pack includes required run_id/trace_id |
| spectrum_systems/modules/governance/done_certification.py | MODIFY | Ensure done certification record includes required run_id |
| tests/test_artifact_lineage.py | MODIFY | Update stale local fixture helper to current artifact_lineage contract |
| tests/test_release_canary.py | MODIFY | Update stale eval_result fixture helper to include required run_id identity field |
| tests/test_slo_control.py | MODIFY | Update stale lineage fixture helpers to emit required identity + graph fields |

## Contracts touched
None (consumer/builder alignment only).

## Tests that must pass after execution
1. `pytest tests/test_artifact_lineage.py`
2. `pytest tests/test_control_loop_certification.py`
3. `pytest tests/test_done_certification.py`
4. `pytest tests/test_release_canary.py`
5. `pytest tests/test_slo_control.py`

## Scope exclusions
- Do not modify schemas under `contracts/schemas/`.
- Do not weaken schema validation or remove required fields.
- Do not perform unrelated refactors or broad fixture rewrites.

## Dependencies
- Existing canonical schemas/examples for artifact_lineage, control_loop_certification_pack, and done_certification_record are authoritative.

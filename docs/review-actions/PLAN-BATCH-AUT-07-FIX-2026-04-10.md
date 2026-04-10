# Plan — BATCH-AUT-07-FIX — 2026-04-10

## Prompt type
BUILD

## Roadmap item
BATCH-AUT-07-FIX

## Objective
Repair AUT-07 lineage example artifact authenticity/linkage mismatch without changing runtime logic, then resume governed execution from AUT-07 and capture fail-closed progression evidence.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-AUT-07-FIX-2026-04-10.md | CREATE | Required plan-first governance for >2 file change scope. |
| contracts/examples/build_admission_record.example.json | MODIFY | Repair authenticity payload digest and lineage fields to align with canonical runtime verification. |
| contracts/examples/normalized_execution_request.example.json | MODIFY | Repair authenticity payload digest and cross-artifact linkage consistency. |
| contracts/examples/tlc_handoff_record.example.json | MODIFY | Repair trace/request/ref/authenticity consistency to pass repo-write lineage guard. |
| docs/reviews/RVW-BATCH-AUT-07-FIX.md | CREATE | Required review artifact documenting AUT-07 repair outcome and trust verdict. |
| docs/reviews/BATCH-AUT-07-FIX-DELIVERY-REPORT.md | CREATE | Required delivery report with changed fields, validation results, and resumed execution status. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python -c "import json; from spectrum_systems.modules.runtime.repo_write_lineage_guard import validate_repo_write_lineage; adm=json.load(open('contracts/examples/build_admission_record.example.json')); req=json.load(open('contracts/examples/normalized_execution_request.example.json')); handoff=json.load(open('contracts/examples/tlc_handoff_record.example.json')); validate_repo_write_lineage(build_admission_record=adm, normalized_execution_request=req, tlc_handoff_record=handoff, expected_trace_id=adm['trace_id'])"`
2. `pytest tests/test_execution_hierarchy.py -q`
3. `pytest tests/test_pqx_repo_write_lineage_guard.py -q`
4. Resume from AUT-07 by executing AUT-07 → AUT-10 commands from `contracts/roadmap/slice_registry.json` under `contracts/roadmap/roadmap_structure.json` with fail-closed stop on first failure.

## Scope exclusions
- Do not modify runtime logic under `spectrum_systems/modules/runtime/`.
- Do not weaken authenticity or lineage validation.
- Do not modify `contracts/roadmap/slice_registry.json` or `contracts/roadmap/roadmap_structure.json`.
- Do not patch AUT-08+ behavior unless/until execution reaches a concrete failure in that slice.

## Dependencies
- Existing canonical runtime behavior in `spectrum_systems/modules/runtime/repo_write_lineage_guard.py` and `spectrum_systems/modules/runtime/lineage_authenticity.py` remains authoritative.

# Plan — BATCH-AEX-06 — 2026-04-08

## Prompt type
BUILD

## Roadmap item
BATCH-AEX-06

## Objective
Formalize the AEX→TLC repo-mutation handoff as a governed `tlc_handoff_record` artifact contract and enforce fail-closed TLC/PQX lineage usage without expanding AEX or redesigning TLC.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/tlc_handoff_record.schema.json | CREATE | Add canonical contract for TLC handoff artifact. |
| contracts/examples/tlc_handoff_record.example.json | CREATE | Provide governed golden example for schema validation and docs. |
| contracts/standards-manifest.json | MODIFY | Register new artifact contract/version metadata. |
| spectrum_systems/modules/runtime/repo_write_lineage_guard.py | MODIFY | Validate `tlc_handoff_record` contract and required lineage fields fail-closed. |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY | Build/use `tlc_handoff_record` for repo-mutating orchestration handoff. |
| tests/test_tlc_handoff_schema_validation.py | CREATE | Verify schema acceptance/rejection behavior. |
| tests/test_tlc_handoff_flow.py | CREATE | Verify runtime handoff creation, fail-closed behavior, trace continuity, lineage refs, and no direct PQX bypass regression. |
| docs/architecture/system_registry.md | MODIFY | Add `tlc_handoff_record` in runtime path and TLC seam clarification. |
| docs/architecture/foundation_pqx_eval_control.md | MODIFY | Add concise contractization note for AEX→TLC seam. |

## Contracts touched
- Add `tlc_handoff_record` schema and example.
- Update `contracts/standards-manifest.json` with new contract registration and version metadata.

## Tests that must pass after execution
1. `pytest tests/test_tlc_handoff_schema_validation.py tests/test_tlc_handoff_flow.py`
2. `pytest tests/test_tlc_requires_admission_for_repo_write.py tests/test_pqx_repo_write_lineage_guard.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not expand AEX responsibilities or duplicate admission policy inside TLC.
- Do not redesign TLC state machine/orchestration framework.
- Do not add new orchestration behavior beyond formal handoff artifactization.
- Do not introduce alternative repo-write handoff artifact types.

## Dependencies
- Existing AEX admission artifacts (`build_admission_record`, `normalized_execution_request`) remain authoritative prerequisites.

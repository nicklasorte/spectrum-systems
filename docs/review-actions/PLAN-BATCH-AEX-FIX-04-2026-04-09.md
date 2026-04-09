# Plan — BATCH-AEX-FIX-04 — 2026-04-09

## Prompt type
PLAN

## Roadmap item
BATCH-AEX-FIX-04

## Objective
Add deterministic authenticity attestation to AEX/TLC repo-write lineage artifacts and enforce verification fail-closed at the PQX lineage validator boundary.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-AEX-FIX-04-2026-04-09.md | CREATE | Record required PLAN before multi-file BUILD changes. |
| spectrum_systems/modules/runtime/lineage_authenticity.py | CREATE | Add minimal deterministic canonical-digest + HMAC attestation helper for lineage artifacts. |
| spectrum_systems/aex/engine.py | MODIFY | Emit authenticity for `normalized_execution_request` and `build_admission_record`. |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY | Emit authenticity for `tlc_handoff_record`. |
| spectrum_systems/modules/runtime/repo_write_lineage_guard.py | MODIFY | Verify authenticity for all three lineage artifacts fail-closed at authoritative PQX boundary. |
| contracts/schemas/build_admission_record.schema.json | MODIFY | Add required `authenticity` object contract for admission lineage artifact. |
| contracts/schemas/normalized_execution_request.schema.json | MODIFY | Add required `authenticity` object contract for normalized request lineage artifact. |
| contracts/schemas/tlc_handoff_record.schema.json | MODIFY | Add required `authenticity` object contract for TLC handoff lineage artifact. |
| contracts/examples/build_admission_record.example.json | MODIFY | Add authenticity example fields. |
| contracts/examples/normalized_execution_request.example.json | MODIFY | Add authenticity example fields. |
| contracts/examples/tlc_handoff_record.example.json | MODIFY | Add authenticity example fields. |
| docs/architecture/system_registry.md | MODIFY | Minimally document authenticity requirement on repo-write lineage artifacts. |
| tests/conftest.py | CREATE | Provide deterministic test attestation secret setup for repo-write lineage tests. |
| tests/test_pqx_repo_write_lineage_guard.py | MODIFY | Add regression coverage for missing/forged authenticity rejection at PQX boundary. |
| tests/test_aex_admission.py | MODIFY | Assert AEX lineage artifacts include authenticity fields. |
| tests/test_tlc_handoff_flow.py | MODIFY | Keep TLC handoff flow fixtures valid with signed lineage artifacts. |
| tests/test_pqx_handoff_adapter.py | MODIFY | Keep repo-write handoff fixtures valid with signed lineage artifacts. |
| tests/test_pqx_slice_runner.py | MODIFY | Keep PQX slice runner lineage fixtures valid with signed lineage artifacts. |
| tests/test_cycle_runner.py | MODIFY | Keep cycle runner repo-write lineage fixtures valid with signed lineage artifacts. |
| tests/test_tlc_requires_admission_for_repo_write.py | MODIFY | Keep TLC admission enforcement fixtures valid with signed lineage artifacts. |

## Contracts touched
- `build_admission_record`
- `normalized_execution_request`
- `tlc_handoff_record`

## Tests that must pass after execution
1. `pytest tests/test_aex_admission.py tests/test_pqx_repo_write_lineage_guard.py tests/test_tlc_handoff_flow.py tests/test_pqx_handoff_adapter.py tests/test_pqx_slice_runner.py tests/test_cycle_runner.py tests/test_tlc_requires_admission_for_repo_write.py`
2. `pytest tests/test_contracts.py`

## Scope exclusions
- Do not add external KMS, PKI, or distributed trust infrastructure.
- Do not redesign AEX, TLC, or PQX orchestration flow.
- Do not add broad secret-management systems beyond minimal lineage attestation needs.
- Do not refactor unrelated runtime modules.

## Dependencies
- Existing AEX/TLC/PQX lineage guard implementation from BATCH-AEX and BATCH-AEX-06 must remain authoritative.

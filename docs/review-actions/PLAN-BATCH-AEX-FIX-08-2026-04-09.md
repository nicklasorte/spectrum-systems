# Plan — BATCH-AEX-FIX-08 — 2026-04-09

## Prompt type
PLAN

## Roadmap item
BATCH-AEX-FIX-08

## Objective
Make repo-write lineage acceptance authoritative by requiring persisted issuance registry confirmation in addition to schema, continuity, authenticity, freshness, and replay checks.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-AEX-FIX-08-2026-04-09.md | CREATE | Required plan-first record for multi-file change set. |
| spectrum_systems/modules/runtime/lineage_issuance_registry.py | CREATE | Add narrow persisted issuance registry helper for authoritative lineage artifacts. |
| spectrum_systems/modules/runtime/lineage_authenticity.py | MODIFY | Automatically record issuance from authoritative issuer paths when authenticity is issued. |
| spectrum_systems/modules/runtime/repo_write_lineage_guard.py | MODIFY | Require registry-backed issuance confirmation in authoritative repo-write lineage validation. |
| tests/conftest.py | MODIFY | Reset issuance registry state per test for deterministic execution. |
| tests/test_pqx_repo_write_lineage_guard.py | MODIFY | Add regression tests proving forged-but-valid lineage is rejected without authoritative issuance registry confirmation. |
| docs/architecture/foundation_pqx_eval_control.md | MODIFY | Document that PQX repo-write lineage acceptance requires registry-backed authoritative issuance proof. |

## Scope exclusions
- No external KMS or public-key redesign.
- No role changes for AEX/TLC/PQX.
- No generic new platform subsystem.
- No caller-by-caller policy rewrite.

## Validation commands
1. `pytest tests/test_pqx_repo_write_lineage_guard.py`
2. `pytest tests/test_aex_admission.py tests/test_tlc_handoff_flow.py tests/test_pqx_handoff_adapter.py tests/test_pqx_slice_runner.py tests/test_cycle_runner.py tests/test_tlc_requires_admission_for_repo_write.py`
3. `pytest tests/test_contracts.py`

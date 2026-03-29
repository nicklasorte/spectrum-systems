# Plan — B7 FIX EXECUTION AND REINSERTION LOOP — 2026-03-29

## Prompt type
PLAN

## Roadmap item
B7 — PQX fix execution + deterministic reinsertion loop

## Objective
Implement a deterministic fail-closed fix execution loop that converts pending fixes into executable steps, executes them through the PQX sequence backbone, records governed artifacts, updates bundle state, and resumes bundle progression.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-B7-FIX-EXECUTION-2026-03-29.md | CREATE | Required execution plan artifact for multi-file/new-module change. |
| docs/review-actions/B7_EXECUTION_SUMMARY_2026-03-29.md | CREATE | Required execution summary artifact for implemented slice. |
| docs/roadmaps/pqx_fix_execution.md | CREATE | Document lifecycle, insertion rules, failure modes, and replay guarantees. |
| spectrum_systems/modules/runtime/pqx_fix_execution.py | CREATE | New runtime module implementing governed fix loop functions. |
| spectrum_systems/modules/runtime/pqx_bundle_state.py | MODIFY | Extend state initialization and behavior for executed/failed fix tracking fields. |
| spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py | MODIFY | Integrate pre-step pending-fix execution loop and fail-closed advancement gating. |
| scripts/run_pqx_bundle.py | MODIFY | Add `--execute-fixes` CLI behavior and fail/non-zero handling for blocked/failed fixes. |
| contracts/schemas/pqx_fix_execution_record.schema.json | CREATE | New canonical contract for fix execution records. |
| contracts/examples/pqx_fix_execution_record.json | CREATE | Golden-path example for fix execution record contract. |
| contracts/schemas/pqx_bundle_state.schema.json | MODIFY | Add deterministic fix-loop state fields and bump schema version. |
| contracts/examples/pqx_bundle_state.json | MODIFY | Keep example aligned with new bundle-state schema surface. |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump bundle-state contract version metadata. |
| tests/test_pqx_fix_execution.py | CREATE | Required test coverage for normalization, insertion, execution, fail-closed conflicts, replay determinism, and resume behavior. |
| tests/test_pqx_bundle_state.py | MODIFY | Align existing bundle-state tests with schema/state surface additions. |
| tests/test_run_pqx_bundle_cli.py | MODIFY | Add CLI coverage for `--execute-fixes` failure behavior. |

## Contracts touched
- Add `pqx_fix_execution_record` schema + example + standards-manifest entry.
- Update `pqx_bundle_state` schema version and fields for fix execution loop state.

## Tests that must pass after execution
1. `pytest tests/test_pqx_fix_execution.py`
2. `pytest tests/test_pqx_bundle_state.py tests/test_pqx_bundle_orchestrator.py tests/test_run_pqx_bundle_cli.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/contract-boundary-audit/run.sh`
6. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not replace or fork PQX sequence execution; fixes must run via existing runner.
- Do not introduce a second bundle orchestration system.
- Do not mutate previously emitted execution artifacts.
- Do not modify unrelated roadmap execution logic outside fix-loop gating/integration.

## Dependencies
- Existing `pqx_bundle_state`, `pqx_bundle_orchestrator`, `pqx_sequence_runner`, and `pqx_review_result` ingestion flow must remain authoritative and backward compatible.

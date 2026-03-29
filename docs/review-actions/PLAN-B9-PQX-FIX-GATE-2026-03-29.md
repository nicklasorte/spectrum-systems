# Plan — B9 — 2026-03-29

## Prompt type
PLAN

## Roadmap item
B9 — PQX fix-gate integration with bundle progression hard-stop

## Objective
Enforce deterministic, fail-closed fix adjudication so bundle step progression resumes only after governed `pqx_fix_gate_record` artifacts explicitly pass.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/pqx_fix_gate.py | MODIFY | Align fix-gate adjudication logic and emitted artifact structure to B9 contract requirements. |
| spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py | MODIFY | Emit fix execution + fix gate artifacts and enforce resume hard-stop behavior. |
| scripts/run_pqx_bundle.py | MODIFY | Surface fix-gate block context and preserve deterministic exit semantics. |
| spectrum_systems/modules/runtime/pqx_bundle_state.py | MODIFY | Enforce deterministic fix-gate persistence behavior and duplicate handling semantics. |
| contracts/schemas/pqx_fix_gate_record.schema.json | MODIFY | Publish governed fix-gate adjudication contract fields required by B9. |
| contracts/examples/pqx_fix_gate_record.json | MODIFY | Provide canonical golden-path example for the new fix-gate contract. |
| contracts/schemas/pqx_bundle_state.schema.json | MODIFY | Maintain bundle-state schema parity for fix gate persistence fields. |
| contracts/examples/pqx_bundle_state.json | MODIFY | Keep bundle-state example aligned with schema/runtime defaults. |
| contracts/standards-manifest.json | MODIFY | Register new contract metadata/version changes. |
| tests/test_pqx_fix_gate.py | MODIFY | Validate pass/block adjudication semantics and fail-closed behavior. |
| tests/test_pqx_fix_execution.py | MODIFY | Cover fix execution integration expectations with gate compatibility. |
| tests/test_pqx_bundle_state.py | MODIFY | Validate persistence/reload parity for fix gate fields and duplicate behavior. |
| tests/test_pqx_bundle_orchestrator.py | MODIFY | Validate orchestrator gating hard-stop and emitted records. |
| tests/test_run_pqx_bundle_cli.py | MODIFY | Validate CLI non-zero and block context on fix-gate failures. |
| tests/test_contracts.py | MODIFY | Validate schema/example + manifest registration for new/updated contract fields. |
| docs/roadmaps/pqx_fix_gate.md | MODIFY | Document control intent, authoritative artifact, and pass/block conditions. |
| docs/review-actions/B9_EXECUTION_SUMMARY_2026-03-29.md | CREATE | Record B9 implementation/testing/verification evidence. |

## Contracts touched
- `contracts/schemas/pqx_fix_gate_record.schema.json` (field-level contract hardening)
- `contracts/schemas/pqx_bundle_state.schema.json` (fix-gate persistence parity)
- `contracts/standards-manifest.json` (contract registry update)

## Tests that must pass after execution
1. `pytest tests/test_pqx_fix_gate.py tests/test_pqx_fix_execution.py tests/test_pqx_bundle_state.py tests/test_pqx_bundle_orchestrator.py tests/test_run_pqx_bundle_cli.py tests/test_contracts.py`
2. `pytest`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-B9-PQX-FIX-GATE-2026-03-29.md`

## Scope exclusions
- Do not redesign PQX orchestration architecture or add a second control loop.
- Do not broaden into multi-bundle scheduling changes.
- Do not alter unrelated review-generation workflows.
- Do not weaken schema strictness or infer resolution from fix execution exit code.

## Dependencies
- Existing PQX fix execution + bundle orchestration seams must remain authoritative.
- B8 runtime behavior is treated as prior baseline and must remain backward-compatible for non-fix paths.

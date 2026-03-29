# Plan — PQX-FIX-GATE — 2026-03-29

## Prompt type
PLAN

## Roadmap item
PQX fix adjudication gate hardening slice (runtime + contract + CLI)

## Objective
Ensure executed PQX fixes cannot resume bundle step advancement until each fix is adjudicated through a governed `pqx_fix_gate_record` decision with deterministic fail-closed pass/block semantics.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/pqx_fix_gate_record.schema.json | CREATE | New governed contract for fix-gate adjudication artifacts. |
| contracts/examples/pqx_fix_gate_record.json | CREATE | Golden-path example for new fix-gate contract. |
| contracts/schemas/pqx_bundle_state.schema.json | MODIFY | Extend bundle-state contract with fix-gate tracking fields. |
| contracts/examples/pqx_bundle_state.json | MODIFY | Keep bundle-state example aligned with expanded contract. |
| contracts/standards-manifest.json | MODIFY | Register `pqx_fix_gate_record` and bump relevant contract versions. |
| spectrum_systems/modules/runtime/pqx_fix_gate.py | CREATE | Implement deterministic fix completion gate logic and fail-closed checks. |
| spectrum_systems/modules/runtime/pqx_bundle_state.py | MODIFY | Initialize/maintain fix-gate state fields in persisted bundle state. |
| spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py | MODIFY | Wire fix-gate adjudication before post-fix bundle step progression. |
| scripts/run_pqx_bundle.py | MODIFY | Add fix-gate reporting and non-zero exit behavior for unresolved adjudication. |
| tests/test_pqx_fix_gate.py | CREATE | Focused coverage for fix-gate success/failure/replay behavior. |
| tests/test_pqx_fix_execution.py | MODIFY | Align fix-loop expectations with required fix-gate semantics. |
| tests/test_pqx_bundle_state.py | MODIFY | Validate new bundle-state fix-gate fields and defaults. |
| tests/test_pqx_bundle_orchestrator.py | MODIFY | Verify deterministic block/resume behavior through fix-gate outcomes. |
| tests/test_run_pqx_bundle_cli.py | MODIFY | Verify CLI non-zero behavior when fix adjudication blocks. |
| docs/roadmaps/pqx_fix_gate.md | CREATE | Focused roadmap doc for module behavior and failure modes. |
| docs/review-actions/PQX_FIX_GATE_SUMMARY_2026-03-29.md | CREATE | Scope/validation summary artifact for review handoff. |

## Contracts touched
- `contracts/schemas/pqx_fix_gate_record.schema.json` (new)
- `contracts/schemas/pqx_bundle_state.schema.json` (version bump for additive fields)
- `contracts/standards-manifest.json` (publish new/updated versions)

## Tests that must pass after execution
1. `pytest tests/test_pqx_fix_gate.py tests/test_pqx_fix_execution.py tests/test_pqx_bundle_state.py tests/test_pqx_bundle_orchestrator.py tests/test_run_pqx_bundle_cli.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-PQX-FIX-GATE-2026-03-29.md`

## Scope exclusions
- Do not introduce a second independent fix decision path outside `pqx_bundle_orchestrator`.
- Do not refactor unrelated PQX runtime modules.
- Do not alter roadmap authority references or bundle table semantics.

## Dependencies
- Existing PQX fix execution and bundle-state integration slices (B6/B7 lineage) must remain authoritative and unchanged in intent.

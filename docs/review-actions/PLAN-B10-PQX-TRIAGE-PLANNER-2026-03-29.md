# Plan — B10 — 2026-03-29

## Prompt type
PLAN

## Roadmap item
B10 — PQX Review Triage + Rack-and-Stack Planning Engine

## Objective
Add a deterministic, fail-closed, planning-only PQX triage artifact + runtime planner that converts governed review and fix-gate outcomes into a schema-bound rack-and-stack plan without changing existing execution semantics.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/pqx_triage_plan_record.schema.json | CREATE | Define governed schema-first planning artifact contract for B10 triage output. |
| contracts/examples/pqx_triage_plan_record.json | CREATE | Add deterministic golden-path example for new triage planning contract. |
| contracts/standards-manifest.json | MODIFY | Register/version-pin `pqx_triage_plan_record` in authoritative standards manifest. |
| spectrum_systems/modules/runtime/pqx_triage_planner.py | CREATE | Implement deterministic fail-closed triage planning runtime helpers and artifact builder. |
| spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py | MODIFY | Add additive optional triage-plan emission seam tied to review findings/fix-gate block/blocked completion states. |
| scripts/run_pqx_bundle.py | MODIFY | Add CLI surface to emit triage plan after run or from existing artifacts with governed exit behavior. |
| docs/roadmaps/pqx_triage_planner.md | CREATE | Operator-facing documentation for planning-only triage behavior and insertion model. |
| docs/review-actions/B10_EXECUTION_SUMMARY_2026-03-29.md | CREATE | Execution summary artifact for implemented B10 slice and validation evidence. |
| tests/test_pqx_triage_planner.py | CREATE | Focused deterministic/fail-closed/replay-safe planner tests. |
| tests/test_pqx_bundle_orchestrator.py | MODIFY | Add orchestrator wiring tests for optional triage-plan emission conditions. |
| tests/test_run_pqx_bundle_cli.py | MODIFY | Add CLI tests for triage emission modes and blocked/invalid exit codes. |
| tests/test_contracts.py | MODIFY | Add contract example validation coverage for `pqx_triage_plan_record`. |

## Contracts touched
- `contracts/schemas/pqx_triage_plan_record.schema.json` (new contract)
- `contracts/standards-manifest.json` (new registry entry/version pin)

## Tests that must pass after execution
1. `pytest tests/test_pqx_triage_planner.py tests/test_pqx_bundle_orchestrator.py tests/test_run_pqx_bundle_cli.py tests/test_contracts.py -q`
2. `pytest tests/test_contract_enforcement.py -q`
3. `python scripts/run_contract_enforcement.py`
4. `pytest -q`
5. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-B10-PQX-TRIAGE-PLANNER-2026-03-29.md`

## Scope exclusions
- Do not auto-execute inserted or deferred slices from triage output.
- Do not mutate `docs/roadmaps/system_roadmap.md` rows or roadmap authority directly.
- Do not add a second orchestration path, second review pipeline, or second fix adjudication system.
- Do not refactor unrelated runtime modules outside declared seams.

## Dependencies
- B9 slice completion artifacts must already exist and remain the single execution path baseline.

# Plan — BATCH-S2 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-S2 — Self-Testing Foundation (ST-02 + ST-03 + ST-05 + ST-21)

## Objective
Implement governed required-eval coverage contracts and deterministic fail-closed enforcement for the MVP judgment path so missing/indeterminate required eval coverage blocks or freezes progression with explicit coverage artifacts.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-S2-2026-04-04.md | CREATE | Required plan-first execution record for BATCH-S2. |
| PLANS.md | MODIFY | Register active BATCH-S2 plan. |
| contracts/schemas/required_eval_registry.schema.json | CREATE | Governed machine-readable required eval mapping by artifact family. |
| contracts/schemas/eval_coverage_registry.schema.json | CREATE | Governed artifact for per-family required/present eval coverage accounting. |
| contracts/schemas/eval_coverage_signal.schema.json | CREATE | Governed runtime/operator-facing coverage status signal. |
| contracts/schemas/missing_required_eval_enforcement.schema.json | CREATE | Governed fail-closed enforcement outcome artifact for missing required evals. |
| contracts/examples/required_eval_registry.json | CREATE | Deterministic golden-path required eval mapping example. |
| contracts/examples/eval_coverage_registry.json | CREATE | Deterministic golden-path coverage registry example. |
| contracts/examples/eval_coverage_signal.json | CREATE | Deterministic golden-path coverage signal example. |
| contracts/examples/missing_required_eval_enforcement.json | CREATE | Deterministic golden-path enforcement example. |
| contracts/standards-manifest.json | MODIFY | Publish and pin new schema/example contract versions. |
| spectrum_systems/modules/runtime/required_eval_coverage.py | CREATE | Deterministic loader + coverage computation + fail-closed enforcement logic. |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Enforce required eval mapping/results for artifact_release_readiness path without adding a second control path. |
| tests/test_contracts.py | MODIFY | Validate new governed examples/contracts. |
| tests/test_contract_enforcement.py | MODIFY | Assert standards manifest registration for new contracts. |
| tests/test_evaluation_control.py | MODIFY | Add ST-05 fail-closed tests (missing definition/result, indeterminate freeze, happy path). |
| tests/test_system_mvp_validation.py | MODIFY | Validate deterministic coverage signal artifacts in MVP validation path. |
| tests/test_evaluation_auto_generation.py | MODIFY | Regression guard for existing auto-generation behavior with required coverage artifacts in place. |
| tests/test_required_eval_coverage.py | CREATE | Targeted deterministic unit tests for registry load, enforcement, and signal determinism. |

## Contracts touched
- Add: `required_eval_registry` (1.0.0)
- Add: `eval_coverage_registry` (1.0.0)
- Add: `eval_coverage_signal` (1.0.0)
- Add: `missing_required_eval_enforcement` (1.0.0)
- Modify: `contracts/standards-manifest.json` version bump and contract pins

## Tests that must pass after execution
1. `pytest tests/test_contracts.py`
2. `pytest tests/test_contract_enforcement.py`
3. `pytest tests/test_evaluation_control.py`
4. `pytest tests/test_evaluation_auto_generation.py`
5. `pytest tests/test_system_mvp_validation.py`
6. `pytest tests/test_required_eval_coverage.py`
7. `python scripts/run_contract_enforcement.py`
8. `pytest`
9. `python scripts/run_contract_preflight.py --base-ref HEAD~1 --head-ref HEAD --output-dir outputs/contract_preflight`
10. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign PQX execution semantics.
- Do not alter control decision category vocabulary.
- Do not introduce model-dependent decision logic.
- Do not broaden artifact-family rollout beyond MVP-critical family coverage in this batch.

## Dependencies
- Existing artifact release judgment path and cycle runner wiring must remain authoritative.

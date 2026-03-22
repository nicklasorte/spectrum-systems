# Plan — BBB Contract Collision Fix — 2026-03-22

## Prompt type
PLAN

## Roadmap item
BBB Contract Collision Fix (within BN.7 control integration surface)

## Objective
Split BBB failure-derived artifact semantics from legacy executable eval-case semantics by introducing `failure_eval_case` while preserving legacy `eval_case` execution behavior.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BBB-CONTRACT-COLLISION-FIX-2026-03-22.md | CREATE | Required plan-first artifact for multi-file schema/runtime/test repair. |
| PLANS.md | MODIFY | Register new active plan in active plans table. |
| contracts/schemas/failure_eval_case.schema.json | CREATE | Rename BBB failure-derived schema from eval_case to failure_eval_case. |
| contracts/schemas/eval_case.schema.json | MODIFY | Preserve legacy eval_case executable contract for eval engine. |
| contracts/examples/failure_eval_case.json | CREATE | Rename/add BBB failure-derived example aligned to failure_eval_case schema. |
| contracts/examples/eval_case.json | MODIFY | Preserve legacy eval_case executable example used by eval engine. |
| spectrum_systems/modules/runtime/evaluation_auto_generation.py | CREATE | Runtime generator for deterministic fail-closed failure_eval_case artifacts. |
| spectrum_systems/modules/runtime/control_integration.py | MODIFY | Additive integration wiring with `generated_failure_eval_case` key only. |
| contracts/standards-manifest.json | MODIFY | Register failure_eval_case and preserve existing eval_case manifest entry. |
| tests/test_evaluation_auto_generation.py | CREATE | Validate deterministic mapping, schema compliance, and fail-closed behavior. |
| tests/test_control_integration.py | MODIFY | Assert additive generated_failure_eval_case behavior on blocked/failure paths. |

## Contracts touched
- `failure_eval_case` (new canonical BBB failure-derived artifact contract)
- `eval_case` (legacy executable evaluation-case contract preserved)
- `contracts/standards-manifest.json` registry entries for both artifacts

## Tests that must pass after execution
1. `pytest tests/test_eval_engine.py tests/test_evaluation_auto_generation.py tests/test_control_integration.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/check_artifact_boundary.py`
5. `.codex/skills/verify-changed-scope/run.sh`
6. `.codex/skills/contract-boundary-audit/run.sh`
7. `pytest`

## Scope exclusions
- Do not modify `spectrum_systems/modules/evaluation/eval_engine.py`.
- Do not modify `tests/test_eval_engine.py`.
- Do not alter BN.7 enforcement semantics (only additive generated-artifact output key updates).
- Do not loosen schema validation strictness for failure-derived artifact generation.

## Dependencies
- Existing BN.7 control integration behavior remains baseline and must continue passing tests.

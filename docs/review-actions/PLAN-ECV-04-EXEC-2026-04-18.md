# Plan — ECV-04-EXEC — 2026-04-18

## Prompt type
BUILD

## Roadmap item
ECV-04-EXEC — Semantic Eval Coverage + Failure Learning Loop

## Objective
Implement fail-closed semantic eval execution, failure-to-eval conversion, required eval coverage enforcement, red-team blind-spot detection, and regression binding in the WPG execution path.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-ECV-04-EXEC-2026-04-18.md | CREATE | Required multi-file execution plan |
| spectrum_systems/modules/runtime/semantic_eval.py | CREATE | Semantic eval classes and control decision mapping |
| spectrum_systems/modules/runtime/failure_to_eval.py | MODIFY | Failure → eval conversion + regression case generation |
| spectrum_systems/modules/wpg/eval_coverage.py | MODIFY | Enforced stage-boundary eval coverage requirements |
| spectrum_systems/modules/wpg/redteam.py | MODIFY | RTX blind-spot scenarios and findings artifact output |
| spectrum_systems/orchestration/wpg_pipeline.py | MODIFY | Wire semantic evals, conversion loop, coverage enforcement, regression binding |
| contracts/schemas/semantic_eval_result.schema.json | CREATE | Contract for semantic eval execution results |
| contracts/schemas/regression_eval_case.schema.json | CREATE | Contract for permanent regression eval cases |
| contracts/schemas/eval_coverage_requirement_profile.schema.json | CREATE | Contract for stage-level required eval coverage |
| contracts/examples/semantic_eval_result.json | CREATE | Deterministic example payload |
| contracts/examples/regression_eval_case.json | CREATE | Deterministic example payload |
| contracts/examples/eval_coverage_requirement_profile.json | CREATE | Deterministic example payload |
| tests/test_semantic_eval_classes.py | CREATE | ECV-04 semantic eval behavior tests |
| tests/test_failure_to_eval_conversion.py | MODIFY | ECV-05 conversion + regression tests |
| tests/test_eval_coverage_enforcement.py | CREATE | ECV-06 coverage fail-closed enforcement tests |
| tests/test_redteam_eval_blind_spots.py | CREATE | RTX-28 fake-green detection tests |
| tests/test_eval_regressions.py | CREATE | FIX-32 fix binding and recurrence blocking tests |

## Contracts touched
- `contracts/schemas/semantic_eval_result.schema.json` (new)
- `contracts/schemas/regression_eval_case.schema.json` (new)
- `contracts/schemas/eval_coverage_requirement_profile.schema.json` (new)

## Tests that must pass after execution
1. `python -m pytest -q tests/test_semantic_eval_classes.py`
2. `python -m pytest -q tests/test_failure_to_eval_conversion.py`
3. `python -m pytest -q tests/test_eval_coverage_enforcement.py`
4. `python -m pytest -q tests/test_redteam_eval_blind_spots.py`
5. `python -m pytest -q tests/test_eval_regressions.py`
6. `python scripts/run_contract_enforcement.py`
7. `python scripts/run_wpg_pipeline.py --input tests/fixtures/wpg/sample_workflow_loop_input.json`

## Scope exclusions
- Do not change CI workflow files.
- Do not modify unrelated module boundaries.
- Do not alter prompt queue orchestration outside WPG eval-control surfaces.

## Dependencies
- Existing WPG pipeline contracts and runtime control-decision wiring remain authoritative inputs.

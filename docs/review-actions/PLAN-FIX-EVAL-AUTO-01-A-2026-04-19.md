# Plan — FIX-EVAL-AUTO-01-A — 2026-04-19

## Prompt type
BUILD

## Roadmap item
AG-05 follow-up hardening — authority leak closure + admission strictness

## Objective
Remove non-authority vocabulary leaks from the EVAL-AUTO-01 slice, harden admission checks, and add a local guard test to prevent regression.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-FIX-EVAL-AUTO-01-A-2026-04-19.md | CREATE | Required written plan for multi-file BUILD fix |
| spectrum_systems/modules/runtime/failure_eval_generation.py | MODIFY | Neutral vocabulary normalization + fail-closed admission hardening |
| contracts/examples/generated_eval_case.json | MODIFY | Remove authority-shaped values from eval example |
| tests/fixtures/failure_eval_generation_cases.json | MODIFY | Replace authority-shaped values with neutral observational states |
| tests/test_failure_eval_generation.py | MODIFY | Add coverage for normalization and bounded expected_outcome checks |
| tests/test_non_authority_runtime_vocabulary.py | CREATE | Local narrow guard for forbidden authority vocabulary in this slice |
| docs/runtime/eval-auto-01-failure-to-eval.md | MODIFY | Align docs to neutral vocabulary and tighter admission semantics |

## Contracts touched
- `generated_eval_case` (shape update: `input_conditions.failure_state` neutral vocabulary enum)

## Tests that must pass after execution
1. `pytest tests/test_failure_eval_generation.py tests/test_non_authority_runtime_vocabulary.py`
2. `python scripts/run_authority_leak_guard.py --changed-file spectrum_systems/modules/runtime/failure_eval_generation.py --changed-file contracts/examples/generated_eval_case.json --changed-file tests/fixtures/failure_eval_generation_cases.json`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py tests/test_module_architecture.py`

## Scope exclusions
- Do not introduce new system ownership or registry ownership changes.
- Do not weaken existing authority leak guard behavior.
- Do not redesign the broader eval architecture.

## Dependencies
- Existing EVAL-AUTO-01 generated_eval_case and admission record contracts remain in force.

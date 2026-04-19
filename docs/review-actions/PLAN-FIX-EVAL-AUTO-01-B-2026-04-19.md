# Plan — FIX-EVAL-AUTO-01-B — 2026-04-19

## Prompt type
BUILD

## Roadmap item
AG-05 follow-up hardening — authority leak closure B + admission fail-closed tightening

## Objective
Remove remaining lowercase authority-token leakage, strengthen local non-authority vocabulary detection, and tighten admission linkage/type checks.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-FIX-EVAL-AUTO-01-B-2026-04-19.md | CREATE | Required plan for multi-file BUILD fix |
| spectrum_systems/modules/runtime/failure_eval_generation.py | MODIFY | Remove remaining authority literals + stricter admission checks |
| tests/test_non_authority_runtime_vocabulary.py | MODIFY | Case-insensitive forbidden token detection |
| tests/test_failure_eval_generation.py | MODIFY | Add coverage for reason suffix linkage and list-typed replay input requirements |
| docs/runtime/eval-auto-01-failure-to-eval.md | MODIFY | Document tighter admission semantics |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_failure_eval_generation.py tests/test_non_authority_runtime_vocabulary.py`
2. `python scripts/run_authority_leak_guard.py --changed-file spectrum_systems/modules/runtime/failure_eval_generation.py --changed-file tests/test_non_authority_runtime_vocabulary.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py tests/test_module_architecture.py`

## Scope exclusions
- Do not register new authority owners.
- Do not weaken authority guard behavior.
- Do not redesign eval architecture.

## Dependencies
- Existing generated_eval_case schema and manifest registration remain unchanged.

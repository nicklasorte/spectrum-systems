# Plan — EVAL-AUTO-01 — 2026-04-19

## Prompt type
BUILD

## Roadmap item
AG-05 — Failure → Eval Auto-Generation (thin deterministic extension)

## Objective
Add a deterministic failure_record → generated_eval_case generation and admission slice with governed contracts, tests, and runtime documentation.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-EVAL-AUTO-01-2026-04-19.md | CREATE | Required written plan for multi-file BUILD scope |
| contracts/schemas/generated_eval_case.schema.json | CREATE | Governed contract for generated eval artifact |
| contracts/examples/generated_eval_case.json | CREATE | Canonical example artifact for generated_eval_case |
| contracts/schemas/generated_eval_admission_record.schema.json | CREATE | Governed contract for generated eval admission result |
| contracts/examples/generated_eval_admission_record.json | CREATE | Canonical example for admission result |
| contracts/standards-manifest.json | MODIFY | Register new contracts in canonical manifest |
| spectrum_systems/modules/runtime/failure_eval_generation.py | CREATE | Deterministic transformation + admission logic |
| tests/fixtures/failure_eval_generation_cases.json | CREATE | Deterministic fixture inputs for generation/admission tests |
| tests/test_failure_eval_generation.py | CREATE | Focused unit + end-to-end style tests for this slice |
| docs/runtime/eval-auto-01-failure-to-eval.md | CREATE | Runtime-facing additive documentation |

## Contracts touched
- `generated_eval_case` (new)
- `generated_eval_admission_record` (new)
- `standards_manifest` (new contract entries)

## Tests that must pass after execution
1. `pytest tests/test_failure_eval_generation.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `pytest tests/test_module_architecture.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not introduce a new top-level system or registry redesign.
- Do not auto-promote generated evals into required eval coverage.
- Do not alter canonical system ownership boundaries.
- Do not weaken existing fail-closed enforcement behavior.

## Dependencies
- Existing MNT-CHAOS-01 failure_record emission and required eval fail-closed infrastructure must remain unchanged.

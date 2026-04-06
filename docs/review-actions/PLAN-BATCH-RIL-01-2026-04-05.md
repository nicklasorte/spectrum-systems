# Plan — BATCH-RIL-01 — 2026-04-05

## Prompt type
PLAN

## Roadmap item
RIL-001

## Objective
Implement a deterministic, fail-closed review parsing engine that converts structured review and action tracker markdown into schema-backed `review_signal_artifact` outputs.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-RIL-01-2026-04-05.md | CREATE | Required PLAN-first execution record for multi-file contract + module + test slice |
| contracts/schemas/review_signal_artifact.schema.json | CREATE | Define authoritative JSON Schema contract for review signal artifacts |
| contracts/examples/review_signal_artifact.json | CREATE | Provide deterministic golden-path example artifact for the new contract |
| contracts/standards-manifest.json | MODIFY | Register `review_signal_artifact` contract and bump manifest version |
| spectrum_systems/modules/runtime/review_parsing_engine.py | CREATE | Implement deterministic parsing engine and fail-closed extraction logic |
| tests/test_review_parsing_engine.py | CREATE | Add deterministic tests for extraction correctness, fail-closed behavior, and traceability |

## Contracts touched
- `contracts/schemas/review_signal_artifact.schema.json` (new)
- `contracts/standards-manifest.json` (version bump + contract registration)

## Tests that must pass after execution
1. `pytest tests/test_review_parsing_engine.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`

## Scope exclusions
- Do not modify existing review/action markdown source files under `docs/reviews/` or `docs/review-actions/`.
- Do not implement AI/NLP or heuristic parsing; only explicit structured parsing rules are in scope.
- Do not refactor unrelated runtime modules or existing contract schemas.

## Dependencies
- None.

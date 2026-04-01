# Plan — ALIGNMENT-020-FIX-UNIQUE-REFS — 2026-04-01

## Prompt type
PLAN

## Roadmap item
ALIGNMENT-020 follow-up surgical preflight artifact determinism fix

## Objective
Fix duplicate `trace.refs_attempted` emission in contract preflight artifacts by centralizing deterministic deduplication while preserving ordered debug history and schema compliance.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-ALIGNMENT-020-FIX-UNIQUE-REFS-2026-04-01.md | CREATE | Record scoped deterministic bug-fix plan. |
| PLANS.md | MODIFY | Register this active preflight bug-fix plan. |
| scripts/run_contract_preflight.py | MODIFY | Centralize refs_attempted normalization (dedupe + stable order) before artifact output. |
| tests/test_contract_preflight.py | MODIFY | Add targeted regression proving duplicate refs collapse deterministically without dropping distinct refs. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_contract_preflight.py -q`
2. `python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight`
3. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- No schema changes.
- No strategy-gate semantics changes.
- No unrelated refactors.

## Dependencies
- Must preserve fail-closed behavior and schema validation in existing preflight flow.

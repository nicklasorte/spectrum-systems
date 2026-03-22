# Plan — BBC Review 2 Admission Fixes — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt BBC — Eval Registry + Dataset Governance

## Objective
Restore deterministic and fail-closed behavior for eval dataset membership, dataset construction, and registry snapshot governance consistency.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BBC-REVIEW-2-ADMISSION-FIX-2026-03-22.md | CREATE | Record execution scope for required multi-file governance fixes |
| PLANS.md | MODIFY | Register this plan in active plans table |
| spectrum_systems/modules/evaluation/eval_dataset_registry.py | MODIFY | Implement deterministic duplicate handling, fail-closed membership checks, and snapshot policy integrity validation |
| tests/test_eval_dataset_registry.py | MODIFY | Add/adjust unit tests for permutation invariance, manual-case policy, provenance semantics, snapshot mismatch rejection, and malformed membership rejection |
| tests/test_build_eval_registry_snapshot_cli.py | MODIFY | Add CLI-level snapshot mismatch rejection coverage |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q tests/test_eval_dataset_registry.py tests/test_build_eval_registry_snapshot_cli.py`
2. `pytest -q tests/test_contracts.py`

## Scope exclusions
- Do not add new artifact families or schemas.
- Do not refactor unrelated evaluation modules.
- Do not change CLI interface shape beyond fail-closed behavior.

## Dependencies
- docs/review-actions/PLAN-BBC-2026-03-22.md must remain authoritative for broader BBC scope.

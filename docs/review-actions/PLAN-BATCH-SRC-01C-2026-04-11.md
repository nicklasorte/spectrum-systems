# Plan — BATCH-SRC-01C — 2026-04-11

## Prompt type
BUILD

## Roadmap item
BATCH-SRC-01C

## Objective
Add a minimal deterministic helper to refresh `tpa_scope_policy` source-authority digests and pin policy metadata to live source-index digests without weakening fail-closed validation.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-SRC-01C-2026-04-11.md | CREATE | Required multi-file execution plan. |
| scripts/refresh_tpa_source_authority_digests.py | CREATE | Deterministic digest refresh helper. |
| tests/test_refresh_tpa_source_authority_digests.py | CREATE | Verify helper determinism and digest alignment behavior. |
| config/policy/tpa_scope_policy.json | MODIFY | Refresh source_authority_refresh metadata using helper output. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_refresh_tpa_source_authority_digests.py`
2. `pytest tests/test_tpa_scope_policy.py`
3. `pytest tests/test_tpa_sequence_runner.py`
4. `pytest tests/test_top_level_conductor.py`
5. `pytest tests/test_system_end_to_end_governed_loop.py`
6. `pytest tests/test_tlc_requires_admission_for_repo_write.py`
7. `pytest tests/test_system_handoff_integrity.py`

## Scope exclusions
- Do not modify tpa scope fail-closed validation logic.
- Do not alter source indexes beyond digest refresh alignment.
- Do not bypass governance checks.

## Dependencies
- BATCH-SRC-01B changes are present.

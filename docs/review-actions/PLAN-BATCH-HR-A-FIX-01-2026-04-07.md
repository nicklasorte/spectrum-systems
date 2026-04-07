# Plan — BATCH-HR-A-FIX-01 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-HR-A-FIX-01 — Repair contract preflight BLOCK for stage contract spine

## Objective
Repair `run_contract_preflight.py` fail-closed BLOCK for HR-A stage-contract files by adding minimal deterministic preflight recognition logic and focused regression coverage.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| scripts/run_contract_preflight.py | MODIFY | Add explicit stage-contract example→schema resolution for preflight validation. |
| tests/test_contract_preflight.py | MODIFY | Add deterministic regression test proving stage-contract example resolution behavior. |
| docs/review-actions/PLAN-BATCH-HR-A-FIX-01-2026-04-07.md | CREATE | Required plan artifact for multi-file fix. |

## Contracts touched
None (preflight logic and tests only).

## Tests that must pass after execution
1. `pytest tests/test_contract_preflight.py`
2. `pytest tests/test_stage_contract_runtime.py tests/test_sequence_transition_policy.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `python scripts/run_contract_preflight.py --base-ref HEAD~1 --head-ref HEAD --output-dir outputs/contract_preflight_local`

## Scope exclusions
- Do not redesign preflight gate strategy logic.
- Do not weaken required-surface or fail-closed behavior.
- Do not modify trust-spine/control-surface enforcement semantics.
- Do not refactor unrelated modules.

## Dependencies
- Existing HR-A commit remains the baseline under test for this fix.

# Plan — FIX-MNT-CHAOS-01-A — 2026-04-19

## Prompt type
BUILD

## Roadmap item
FIX-MNT-CHAOS-01-A

## Objective
Remove authority-shaped vocabulary from the chaos/failure-intelligence adapter module while preserving deterministic fail-closed observability behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-FIX-MNT-CHAOS-01-A-2026-04-19.md | CREATE | Required written plan for a multi-file BUILD change. |
| spectrum_systems/modules/runtime/chaos_failure_intelligence.py | MODIFY | Normalize authority-shaped enforcement language to neutral observational vocabulary. |
| tests/test_chaos_fail_closed.py | MODIFY | Assert neutral adapter outputs while preserving fail-closed expectations. |
| docs/runtime/mnt-chaos-failure-intelligence.md | MODIFY | Document neutral observational vocabulary used by the adapter layer. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_chaos_fail_closed.py`
2. `pytest tests/test_required_eval_coverage.py`

## Scope exclusions
- Do not change control/authority owner modules.
- Do not modify registry ownership files.
- Do not bypass authority leak guard.

## Dependencies
- Existing fail-closed enforcement output from `enforce_required_eval_coverage` remains authoritative input.

# Plan — BATCH-SYS-ENF-03A — 2026-04-09

## Prompt type
BUILD

## Roadmap item
BATCH-SYS-ENF-03A

## Objective
Repair contract preflight failures introduced by ENF-03 authority collapse through compatibility-safe contract evolution and consumer updates without restoring non-CDE promotion authority.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-SYS-ENF-03A-2026-04-09.md | CREATE | Required multi-file execution plan. |
| contracts/schemas/next_step_decision_artifact.schema.json | MODIFY | Add compatibility bridge for legacy fields while preserving non-authoritative semantics. |
| contracts/examples/next_step_decision_artifact.json | MODIFY | Keep examples schema-valid under compatibility bridge. |
| spectrum_systems/orchestration/next_step_decision.py | MODIFY | Emit compatibility fields as derived legacy outputs (non-authoritative). |
| tests/test_next_step_decision.py | MODIFY | Validate compatibility + non-authoritative fields. |
| tests/test_next_step_decision_policy.py | MODIFY | Repair consumer expectations to support compatibility bridge. |
| tests/test_cycle_runner.py | MODIFY | Add required closure artifact refs and update fail-closed expectations. |
| docs/reviews/BATCH-SYS-ENF-03A-contract-preflight-repair.md | CREATE | Record root cause and compatibility repair rationale. |

## Contracts touched
- next_step_decision_artifact.schema.json

## Tests that must pass after execution
1. `pytest tests/test_next_step_decision.py tests/test_next_step_decision_policy.py tests/test_cycle_runner.py`
2. `python scripts/run_contract_preflight.py --base-ref HEAD~1 --head-ref HEAD --output-dir outputs/contract_preflight`

## Scope exclusions
- Do not reintroduce promotion authority outside CDE.
- Do not revert ENF-03 signal-only TLC semantics.
- Do not redesign orchestration lifecycle states.

## Dependencies
- BATCH-SYS-ENF-03 commit must be present (current HEAD baseline).

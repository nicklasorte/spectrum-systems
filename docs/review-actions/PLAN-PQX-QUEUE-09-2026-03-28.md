# Plan — PQX-QUEUE-09 Queue CLI / Entrypoint Consolidation — 2026-03-28

## Prompt type
PLAN

## Roadmap item
QUEUE-09 — Queue CLI / Entrypoint Consolidation

## Objective
Consolidate queue-loop execution behind one canonical thin CLI entrypoint with deterministic artifact writes and fail-closed exit semantics while preserving existing queue module seams.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-09-2026-03-28.md | CREATE | Required plan-first declaration for this multi-file BUILD slice. |
| scripts/run_prompt_queue.py | MODIFY | Define/normalize canonical queue entrypoint interface and deterministic exit/write behavior. |
| scripts/run_prompt_queue_execution.py | MODIFY | Keep as backward-compatibility wrapper that delegates queue-loop runs to canonical entrypoint when requested. |
| tests/test_prompt_queue_cli_entrypoint.py | CREATE | Add deterministic canonical CLI + compatibility wrapper behavioral coverage. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_cli_entrypoint.py`
2. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify queue transition/execution business logic inside module seams.
- Do not modify replay/resume semantics beyond preserving existing utility behavior.
- Do not add QUEUE-10 certification logic.
- Do not redesign queue contracts.

## Dependencies
- QUEUE-01 through QUEUE-08 contracts and module seams remain authoritative.

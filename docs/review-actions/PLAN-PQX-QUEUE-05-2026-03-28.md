# Plan — [ROW: QUEUE-05] Fail-Closed Execution Loop Orchestration — 2026-03-28

## Prompt type
PLAN

## Roadmap item
[ROW: QUEUE-05] Fail-Closed Execution Loop Orchestration

## Objective
Implement a deterministic, fail-closed single-step queue execution loop that consumes manifest/state artifacts, executes one eligible step through existing QUEUE-01..04 seams, emits governed decisions, and advances or halts with explicit state transitions only.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-05-2026-03-28.md | CREATE | Required plan-first artifact for multi-file BUILD slice. |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Add run_queue_once loop orchestration and governed queue-state transition applier. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export QUEUE-05 loop entrypoints for module-level CLI/test imports. |
| scripts/run_prompt_queue.py | MODIFY | Replace legacy demo flow with thin CLI that loads manifest/state, runs one loop iteration, writes state, and exits non-zero on block/failure. |
| tests/test_prompt_queue_execution_loop.py | CREATE | Add deterministic fail-closed coverage for loop behavior, halt/advance conditions, and no-skip constraints. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_execution_loop.py`
2. `pytest tests/test_prompt_queue_execution_runner.py tests/test_prompt_queue_execution_integration.py tests/test_prompt_queue_transition_decision.py`

## Scope exclusions
- Do not implement retry orchestration (QUEUE-06).
- Do not implement observability aggregation (QUEUE-07).
- Do not implement replay/resume logic (QUEUE-08).
- Do not implement certification flow wiring (QUEUE-10).
- Do not modify queue contracts/schemas in this slice.

## Dependencies
- [ROW: QUEUE-01] Queue manifest/state contract spine complete.
- [ROW: QUEUE-02] Step execution adapter normalization complete.
- [ROW: QUEUE-03] Findings parsing + step decision complete.
- [ROW: QUEUE-04] Transition decision spine complete.

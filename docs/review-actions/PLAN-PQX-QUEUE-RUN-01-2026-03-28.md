# Plan — PQX-QUEUE-RUN-01 — 2026-03-28

## Prompt type
PLAN

## Roadmap item
PQX-QUEUE-RUN-01 — First Sequential Automatic Queue Run

## Objective
Execute a real governed two-step PQX queue run (QUEUE-06 then QUEUE-07) using the existing queue runner, producing schema-valid manifest/state/decision/observability artifacts with fail-closed semantics and deterministic progression evidence.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-RUN-01-2026-03-28.md | CREATE | Required plan-first governance artifact for this multi-file BUILD execution. |
| PLANS.md | MODIFY | Register the active plan in the plan index table. |
| artifacts/prompt_queue/manifests/pqx_queue_run_01.manifest.json | CREATE | Two-step queue manifest for QUEUE-06 and QUEUE-07 governed run. |
| artifacts/prompt_queue/state/pqx_queue_run_01.state.json | CREATE/MODIFY | Initial queue state plus deterministic updates after each queue runner invocation. |
| artifacts/prompt_queue/execution_results/pqx_queue_run_01.step-001.execution_result.json | CREATE | Persist execution result evidence for executed step 1. |
| artifacts/prompt_queue/execution_results/pqx_queue_run_01.step-002.execution_result.json | CREATE | Persist execution result evidence for executed step 2. |
| artifacts/prompt_queue/step_decisions/pqx_queue_run_01.step-001.step_decision.json | CREATE | Persist explicit step decision for step 1. |
| artifacts/prompt_queue/step_decisions/pqx_queue_run_01.step-002.step_decision.json | CREATE | Persist explicit step decision for step 2. |
| artifacts/prompt_queue/transition_decisions/pqx_queue_run_01.step-001.transition_decision.json | CREATE | Persist explicit transition decision allowing progression to step 2. |
| artifacts/prompt_queue/transition_decisions/pqx_queue_run_01.step-002.transition_decision.json | CREATE | Persist explicit transition decision leading to terminal state. |
| artifacts/prompt_queue/observability/pqx_queue_run_01.snapshot.json | CREATE | Queue observability snapshot aligned to final queue state. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/run_prompt_queue.py --manifest-path artifacts/prompt_queue/manifests/pqx_queue_run_01.manifest.json --queue-state-path artifacts/prompt_queue/state/pqx_queue_run_01.state.json` (run twice to terminal state)
2. `python scripts/run_prompt_queue_observability.py --queue-path artifacts/prompt_queue/state/pqx_queue_run_01.state.json --output-path artifacts/prompt_queue/observability/pqx_queue_run_01.snapshot.json`
3. `python -m pytest tests/test_prompt_queue_manifest.py tests/test_prompt_queue_observability.py tests/test_prompt_queue_transition_decision.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify queue contracts or schema definitions.
- Do not modify queue replay/resume logic.
- Do not add certification or multi-queue scheduling behavior.
- Do not weaken fail-closed transition semantics.

## Dependencies
- QUEUE-01 through QUEUE-07 seams must already exist and remain authoritative for this run.

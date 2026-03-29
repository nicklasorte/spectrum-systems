# Plan — PQX-QUEUE-RUN-02 — 2026-03-29

## Prompt type
PLAN

## Roadmap item
PQX-QUEUE-RUN-02 — governed sequential PQX execution with continuity checks and resumable state (2–3 slice proof)

## Objective
Implement a deterministic, fail-closed sequential execution bridge that runs a small ordered batch of PQX slices (2–3), persists canonical queue-run state after every step, and safely resumes without re-running completed slices by default.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-RUN-02-2026-03-29.md | CREATE | Required plan artifact before multi-file BUILD work. |
| PLANS.md | MODIFY | Register the new active plan entry. |
| contracts/schemas/prompt_queue_sequence_run.schema.json | CREATE | Canonical governed contract for persisted sequential queue-run state. |
| contracts/examples/prompt_queue_sequence_run.json | CREATE | Golden-path example for the new sequence-run contract. |
| contracts/standards-manifest.json | MODIFY | Register new contract and version bump for standards publication. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | CREATE | Deterministic runtime module for sequential execution, continuity checks, persistence, and resume. |
| spectrum_systems/modules/runtime/__init__.py | MODIFY | Export sequence runner interfaces for repo-native consumption. |
| scripts/run_prompt_queue_sequence.py | CREATE | Narrow CLI entrypoint for sequential execution and resume flows. |
| tests/test_pqx_sequence_runner.py | CREATE | Focused runtime tests for happy path, fail-closed continuity, resume, and persistence semantics. |
| tests/test_prompt_queue_sequence_cli.py | CREATE | Focused CLI behavior tests for success/failure exit codes and deterministic output. |
| tests/test_contracts.py | MODIFY | Add contract example validation coverage for prompt_queue_sequence_run. |
| docs/architecture/pqx-sequential-execution-slice.md | CREATE | Short design/contract documentation for semantics, continuity, and intentional 2–3 slice scope boundary. |

## Contracts touched
- Create `prompt_queue_sequence_run` JSON Schema in `contracts/schemas/`.
- Add `prompt_queue_sequence_run` example in `contracts/examples/`.
- Update `contracts/standards-manifest.json` with new contract registration and manifest version bump.

## Tests that must pass after execution
1. `pytest tests/test_pqx_sequence_runner.py tests/test_prompt_queue_sequence_cli.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `pytest`

## Scope exclusions
- Do not add parallel execution or generalized N-scale optimization.
- Do not introduce schedulers, workers, or distributed orchestration.
- Do not redesign existing prompt queue state machine.
- Do not weaken fail-closed identity/continuity enforcement.
- Do not change unrelated prompt queue/review loop policy modules.

## Dependencies
- Existing prompt-queue execution seams from QUEUE-01/02/04 must remain authoritative and be reused.

# Plan — PQX-QUEUE-08 Replay and Resume Checkpoints — 2026-03-28

## Prompt type
PLAN

## Roadmap item
QUEUE-08 — Replay and Resume Checkpoints

## Objective
Implement deterministic, fail-closed, artifact-backed queue resume checkpoints and queue-scoped replay parity validation using existing replay/lineage seams.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-08-2026-03-28.md | CREATE | Required plan-first declaration for multi-file + new schemas change. |
| contracts/schemas/prompt_queue_resume_checkpoint.schema.json | CREATE | New governed contract for validated resume checkpoints. |
| contracts/examples/prompt_queue_resume_checkpoint.json | CREATE | Golden-path checkpoint example. |
| contracts/schemas/prompt_queue_replay_record.schema.json | CREATE | New governed contract for queue-scoped replay parity record. |
| contracts/examples/prompt_queue_replay_record.json | CREATE | Golden-path replay record example. |
| contracts/standards-manifest.json | MODIFY | Register new contracts + bump standards artifact version metadata. |
| spectrum_systems/modules/prompt_queue/queue_artifact_io.py | MODIFY | Add checkpoint/replay record validators and deterministic JSON read helper. |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Add checkpoint build/resume/replay entrypoints and fail-closed integrity/parity checks. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export new checkpoint/resume/replay APIs. |
| scripts/run_prompt_queue_resume.py | CREATE | Thin CLI wrapper for resume from checkpoint. |
| scripts/run_prompt_queue_replay.py | CREATE | Thin CLI wrapper for queue replay parity verification. |
| tests/test_contracts.py | MODIFY | Validate new schema examples through contract test surface. |
| tests/test_prompt_queue_replay_resume.py | CREATE | Deterministic behavior/failure-mode tests for checkpoint, resume, replay, and parity mismatches. |

## Contracts touched
- prompt_queue_resume_checkpoint (new)
- prompt_queue_replay_record (new)
- contracts/standards-manifest.json (registry update)

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_replay_resume.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add certification logic.
- Do not add policy backtesting.
- Do not modify core execution/transition policy logic.
- Do not introduce multi-queue scheduling behavior.

## Dependencies
- Existing queue artifacts/contracts from QUEUE-05/06/07 remain authoritative inputs.
- Existing replay engine and trace/lineage helpers are reused as integration seams.

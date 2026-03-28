# Plan — [ROW: QUEUE-03] Report Parsing and Decision Gate Spine — 2026-03-28

## Prompt type
PLAN

## Roadmap item
[ROW: QUEUE-03] Report Parsing and Decision Gate Spine

## Objective
Implement a deterministic fail-closed parsing + decision gate spine that converts `prompt_queue_execution_result` artifacts into normalized findings and a schema-valid `prompt_queue_step_decision` artifact without any queue transition logic.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-03-2026-03-28.md | CREATE | Required plan-first record for multi-file BUILD + new schema/module scope |
| contracts/schemas/prompt_queue_step_decision.schema.json | CREATE | New governed decision artifact contract |
| contracts/examples/prompt_queue_step_decision.json | CREATE | Golden-path example for new decision contract |
| contracts/schemas/prompt_queue_review_parsing_handoff.schema.json | MODIFY | Add decision artifact linkage emitted by handoff |
| contracts/examples/prompt_queue_review_parsing_handoff.json | MODIFY | Keep handoff example aligned with contract |
| contracts/standards-manifest.json | MODIFY | Register new contract + version bumps |
| spectrum_systems/modules/prompt_queue/review_parser.py | MODIFY | Add deterministic queue-step execution report parsing entrypoint |
| spectrum_systems/modules/prompt_queue/findings_normalizer.py | MODIFY | Enforce bounded finding enums + normalized findings structure |
| spectrum_systems/modules/prompt_queue/findings_artifact_io.py | MODIFY | Harden read/write validation and deterministic serialization |
| spectrum_systems/modules/prompt_queue/step_decision.py | CREATE | Deterministic decision builder with fail-closed rules |
| spectrum_systems/modules/prompt_queue/review_parsing_handoff.py | MODIFY | Wire parse output into decision artifact emission |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export new decision builder/validators |
| tests/test_prompt_queue_step_decision.py | CREATE | Mandatory decision-spine tests for allow/warn/block/fail-closed semantics |
| tests/test_prompt_queue_review_parsing_handoff.py | MODIFY | Assert handoff emits decision artifact path/payload |

## Contracts touched
- Create `prompt_queue_step_decision` (new schema + example + manifest entry).
- Modify `prompt_queue_review_parsing_handoff` schema/example for decision lineage surface.

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_step_decision.py`
2. `pytest tests/test_prompt_queue_review_parsing_handoff.py tests/test_prompt_queue_review_parsing.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add queue advancement/transition logic.
- Do not add retry policy behavior.
- Do not mutate queue state in parsing/decision builders.
- Do not refactor unrelated modules/contracts.

## Dependencies
- `docs/review-actions/PLAN-PQX-QUEUE-02-2026-03-28.md` must be complete for execution result artifact availability.

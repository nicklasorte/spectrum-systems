# Plan — Governed Prompt Queue Review Parsing Handoff — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt slice (governed prompt queue): review invocation output_reference handoff into parsing/findings pipeline

## Objective
Implement a deterministic, fail-closed handoff from successful `prompt_queue_review_invocation_result` artifacts into the existing review parser/findings flow, emitting a schema-backed handoff artifact and minimal queue state updates.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REVIEW-PARSING-HANDOFF-2026-03-22.md | CREATE | Record declared scope before BUILD changes. |
| PLANS.md | MODIFY | Register this plan in active plans table. |
| contracts/schemas/prompt_queue_review_parsing_handoff.schema.json | CREATE | Contract-first schema for handoff lineage artifact. |
| contracts/examples/prompt_queue_review_parsing_handoff.json | CREATE | Golden-path example for handoff artifact validation. |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add handoff artifact path field and optional handoff-aware status support. |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Align embedded work item shape with handoff field/status support. |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Keep work-item example compliant with updated schema. |
| contracts/examples/prompt_queue_state.json | MODIFY | Keep queue-state example compliant with updated schema. |
| contracts/standards-manifest.json | MODIFY | Register new handoff contract and bump versions. |
| spectrum_systems/modules/prompt_queue/review_parsing_handoff.py | CREATE | Pure handoff validation + parser adapter orchestration module. |
| spectrum_systems/modules/prompt_queue/review_parsing_handoff_artifact_io.py | CREATE | Schema validation + write path for handoff artifacts. |
| spectrum_systems/modules/prompt_queue/review_parsing_handoff_queue_integration.py | CREATE | Deterministic queue/work-item mutation for handoff and findings linkage. |
| spectrum_systems/modules/prompt_queue/queue_artifact_io.py | MODIFY | Add schema validator entrypoint for handoff artifacts. |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add work item field + status enum entry as needed. |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Add minimal legal transition(s) for invocation-success to findings-parsed path. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export new handoff, IO, and queue integration API. |
| scripts/run_prompt_queue_review_parsing_handoff.py | CREATE | Thin CLI for end-to-end handoff flow. |
| tests/test_prompt_queue_review_parsing_handoff.py | CREATE | Focused fail-closed and deterministic handoff tests. |
| docs/reviews/governed_prompt_queue_review_parsing_handoff_report.md | CREATE | Required implementation report artifact. |

## Contracts touched
- prompt_queue_review_parsing_handoff (new)
- prompt_queue_work_item (additive)
- prompt_queue_state (embedded work-item alignment)
- standards_manifest (new contract registration + version updates)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_review_parsing_handoff.py`
2. `pytest -q tests/test_prompt_queue_live_review_invocation.py tests/test_prompt_queue_review_parsing.py tests/test_prompt_queue_loop_control.py tests/test_prompt_queue_next_step.py tests/test_prompt_queue_post_execution.py tests/test_prompt_queue_execution.py tests/test_prompt_queue_repair_prompt_generation.py tests/test_prompt_queue_mvp.py`
3. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add new provider calls or modify provider invocation behavior.
- Do not implement retry logic or retry scheduling.
- Do not implement queue-wide scheduling/orchestration changes.
- Do not redesign review parser or findings normalizer behavior.
- Do not implement PR automation or downstream repair-loop changes.

## Dependencies
- docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-LIVE-REVIEW-INVOCATION-IMPLEMENTATION-2026-03-22.md
- docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REVIEW-PARSING-2026-03-22.md

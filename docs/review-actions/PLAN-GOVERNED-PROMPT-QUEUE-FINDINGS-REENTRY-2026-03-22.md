# Plan — Governed Prompt Queue Findings Reentry Wiring — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt slice (governed prompt queue): findings-to-repair reentry wiring from live review loop

## Objective
Implement deterministic, fail-closed reentry wiring that admits only lineage-valid findings from live review parsing handoff into the existing repair prompt generation path, emits a schema-backed reentry artifact, and performs minimal queue/work-item mutation.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-FINDINGS-REENTRY-2026-03-22.md | CREATE | Record plan scope before BUILD changes. |
| PLANS.md | MODIFY | Register this plan in active plans table. |
| contracts/schemas/prompt_queue_findings_reentry.schema.json | CREATE | Contract-first schema for findings-to-repair reentry lineage artifact. |
| contracts/examples/prompt_queue_findings_reentry.json | CREATE | Golden-path example for new reentry artifact contract. |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add nullable findings_reentry_artifact_path field. |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Keep embedded work-item contract aligned with new field. |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Keep example valid after work-item contract update. |
| contracts/examples/prompt_queue_state.json | MODIFY | Keep queue-state example valid after contract update. |
| contracts/standards-manifest.json | MODIFY | Register reentry contract and bump affected contract versions. |
| spectrum_systems/modules/prompt_queue/findings_reentry.py | CREATE | Pure lineage validation + findings-to-repair adapter orchestration. |
| spectrum_systems/modules/prompt_queue/findings_reentry_artifact_io.py | CREATE | Pure schema validation and deterministic write for reentry artifact. |
| spectrum_systems/modules/prompt_queue/findings_reentry_queue_integration.py | CREATE | Deterministic queue/work-item update and duplicate reentry enforcement. |
| spectrum_systems/modules/prompt_queue/queue_artifact_io.py | MODIFY | Add validator entrypoint for prompt_queue_findings_reentry artifacts. |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add findings reentry path field and defaults in queue model factory. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export new reentry modules. |
| scripts/run_prompt_queue_findings_reentry.py | CREATE | Thin CLI for reentry flow over one queue work item. |
| tests/test_prompt_queue_findings_reentry.py | CREATE | Focused tests for reentry completion, fail-closed behavior, and deterministic queue mutation. |
| docs/reviews/governed_prompt_queue_findings_reentry_report.md | CREATE | Mandatory implementation report artifact. |

## Contracts touched
- prompt_queue_findings_reentry (new)
- prompt_queue_work_item (additive)
- prompt_queue_state (embedded work-item alignment)
- standards_manifest (new contract registration + version updates)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_findings_reentry.py`
2. `pytest -q tests/test_prompt_queue_review_parsing_handoff.py tests/test_prompt_queue_live_review_invocation.py tests/test_prompt_queue_review_trigger.py tests/test_prompt_queue_loop_control.py tests/test_prompt_queue_next_step.py tests/test_prompt_queue_post_execution.py tests/test_prompt_queue_execution.py tests/test_prompt_queue_repair_prompt_generation.py tests/test_prompt_queue_review_parsing.py tests/test_prompt_queue_mvp.py`
3. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add new provider calls.
- Do not modify review invocation behavior or parsing model design.
- Do not implement retries, retry scheduling, or queue-wide orchestration.
- Do not redesign existing findings or repair prompt generators.
- Do not implement PR automation or downstream child-spawn redesign.

## Dependencies
- docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REPAIR-PROMPT-2026-03-22.md
- docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-LIVE-REVIEW-INVOCATION-IMPLEMENTATION-2026-03-22.md
- docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REVIEW-PARSING-HANDOFF-2026-03-22.md

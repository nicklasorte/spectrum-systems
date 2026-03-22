# Plan — Governed Prompt Queue Loop Continuation Polish — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt slice (governed prompt queue): child spawn + loop continuation polish for reentry-generated repair prompts

## Objective
Implement deterministic, fail-closed continuation evaluation that consumes lineage-valid findings reentry + repair prompt artifacts, reuses existing repair-child creation, prevents duplicate spawn across repeated cycles, emits a schema-backed continuation artifact, and applies minimal queue/work-item updates.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-LOOP-CONTINUATION-POLISH-2026-03-22.md | CREATE | Record plan scope before BUILD changes. |
| PLANS.md | MODIFY | Register this plan in active plans table. |
| contracts/schemas/prompt_queue_loop_continuation.schema.json | CREATE | Contract-first continuation artifact schema. |
| contracts/examples/prompt_queue_loop_continuation.json | CREATE | Golden-path continuation artifact example. |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add nullable loop_continuation_artifact_path field. |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Align embedded work-item schema with new continuation field. |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Keep work-item example schema-valid after field addition. |
| contracts/examples/prompt_queue_state.json | MODIFY | Keep queue-state example schema-valid after field addition. |
| contracts/standards-manifest.json | MODIFY | Register continuation contract and bump touched contract versions. |
| spectrum_systems/modules/prompt_queue/queue_artifact_io.py | MODIFY | Add validator entrypoint for loop continuation artifacts. |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add loop continuation path field and default model wiring. |
| spectrum_systems/modules/prompt_queue/loop_continuation.py | CREATE | Pure continuation eligibility + lineage validation + child spawn orchestration. |
| spectrum_systems/modules/prompt_queue/loop_continuation_artifact_io.py | CREATE | Pure continuation artifact validation and deterministic write path helpers. |
| spectrum_systems/modules/prompt_queue/loop_continuation_queue_integration.py | CREATE | Deterministic queue/work-item mutation for continuation outcome. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export continuation modules for CLI/tests. |
| scripts/run_prompt_queue_loop_continuation.py | CREATE | Thin CLI for one-item continuation processing. |
| tests/test_prompt_queue_loop_continuation.py | CREATE | Focused continuation behavior coverage and schema guarantees. |
| docs/reviews/governed_prompt_queue_loop_continuation_report.md | CREATE | Mandatory implementation report artifact. |

## Contracts touched
- prompt_queue_loop_continuation (new)
- prompt_queue_work_item (additive)
- prompt_queue_state (embedded work-item alignment)
- standards_manifest (new contract registration + version updates)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_loop_continuation.py`
2. `pytest -q tests/test_prompt_queue_findings_reentry.py tests/test_prompt_queue_review_parsing_handoff.py tests/test_prompt_queue_live_review_invocation.py tests/test_prompt_queue_review_trigger.py tests/test_prompt_queue_loop_control.py tests/test_prompt_queue_repair_child_creation.py tests/test_prompt_queue_execution.py tests/test_prompt_queue_mvp.py`
3. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not introduce retries or queue-wide scheduling.
- Do not invoke review providers or alter provider selection.
- Do not redesign repair child creation or loop-control policy modules.
- Do not add PR automation or downstream deployment/runtime changes.

## Dependencies
- docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-FINDINGS-REENTRY-2026-03-22.md
- docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REPAIR-CHILD-CREATION-2026-03-22.md
- docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-LOOP-CONTROL-2026-03-22.md

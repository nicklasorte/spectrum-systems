# Plan — Governed Prompt Queue MVP — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt slice (module-first MVP): Governed prompt queue orchestration backbone

## Objective
Implement a governed prompt queue MVP that models work items, enforces deterministic lifecycle transitions, orchestrates Claude→Codex fallback behavior, and emits schema-validated queue/work-item/review-attempt artifacts.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-MVP-2026-03-22.md | CREATE | Record execution scope before BUILD work. |
| PLANS.md | MODIFY | Register this new plan in the active plans table. |
| contracts/schemas/prompt_queue_work_item.schema.json | CREATE | Contract-first schema for queue work item artifacts. |
| contracts/schemas/prompt_queue_state.schema.json | CREATE | Contract-first schema for queue state artifacts. |
| contracts/schemas/prompt_queue_review_attempt.schema.json | CREATE | Contract-first schema for review attempt artifacts. |
| contracts/examples/prompt_queue_work_item.json | CREATE | Golden-path work item fixture/example. |
| contracts/examples/prompt_queue_state.json | CREATE | Golden-path queue state fixture/example. |
| contracts/examples/prompt_queue_review_attempt.json | CREATE | Golden-path review attempt fixture/example. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and bump standards manifest version metadata. |
| spectrum_systems/modules/prompt_queue/__init__.py | CREATE | Module export surface for prompt queue MVP. |
| spectrum_systems/modules/prompt_queue/queue_models.py | CREATE | Pure work-item/queue/review-attempt model constructors and enums. |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | CREATE | Deterministic, fail-closed transition validation logic. |
| spectrum_systems/modules/prompt_queue/review_provider_orchestrator.py | CREATE | Provider selection and Claude→Codex fallback orchestration logic. |
| spectrum_systems/modules/prompt_queue/queue_artifact_io.py | CREATE | Schema validation + artifact serialization helpers. |
| scripts/run_prompt_queue.py | CREATE | Thin CLI entrypoint for queue create + review run + artifact emission. |
| tests/test_prompt_queue_mvp.py | CREATE | Focused schema/state-machine/provider/artifact tests for MVP guarantees. |
| docs/reviews/governed_prompt_queue_mvp_report.md | CREATE | Implementation report artifact required by delivery contract. |

## Contracts touched
- prompt_queue_work_item (new)
- prompt_queue_state (new)
- prompt_queue_review_attempt (new)
- standards_manifest (version metadata + new contract entries)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_mvp.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `pytest`

## Scope exclusions
- Do not implement live Claude/Codex API integrations.
- Do not implement full build/review/repair workflow automation.
- Do not add dependency scheduling, queue parallelism, or merge automation.
- Do not parse review markdown or generate repair prompts.

## Dependencies
- Existing contract loader (`spectrum_systems.contracts`) and schema governance flows remain authoritative and are reused as-is.

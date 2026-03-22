# Plan — GOVERNED-PROMPT-QUEUE-LIVE-REVIEW-INVOCATION-FOUNDATION — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Active roadmap alignment: governed prompt queue live review invocation MVP foundation hardening

## Objective
Establish schema/model/state-machine foundations for safe future live review invocation by enforcing Codex-first provider policy, introducing minimal invocation states, defining a review invocation result contract, and wiring persisted invocation-result linkage/idempotency guard scaffolding.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-LIVE-REVIEW-INVOCATION-FOUNDATION-2026-03-22.md | CREATE | Required PLAN artifact before multi-file BUILD changes. |
| contracts/schemas/prompt_queue_review_invocation_result.schema.json | CREATE | New canonical contract for review invocation result artifacts. |
| contracts/examples/prompt_queue_review_invocation_result.json | CREATE | Golden-path example for the new invocation result contract. |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump manifest version metadata. |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add invocation-result linkage field, provider default correction, and invocation statuses. |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Keep embedded work-item schema aligned with invocation fields and statuses. |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Align example with codex-primary default and new nullable invocation linkage field. |
| contracts/examples/prompt_queue_state.json | MODIFY | Align queue example work item with codex-primary default and new invocation linkage field. |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Update provider default, add minimal invocation statuses, and add persisted invocation linkage field. |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Add minimal invocation transition path from review_triggered through invocation outcomes. |
| spectrum_systems/modules/prompt_queue/review_provider_orchestrator.py | MODIFY | Flip orchestration to codex-primary/claude-fallback assumptions without adding live invocation behavior. |
| spectrum_systems/modules/prompt_queue/queue_artifact_io.py | MODIFY | Add validator helper for new invocation result artifact contract. |
| spectrum_systems/modules/prompt_queue/review_invocation_guard.py | CREATE | Add pure duplicate-invocation guard foundation helper for persisted linkage checks. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export new invocation validation and duplicate-guard helper symbols. |
| tests/test_prompt_queue_mvp.py | MODIFY | Add focused tests for provider default, invocation transitions, and duplicate guard helper behavior. |
| tests/test_contracts.py | MODIFY | Validate new invocation result example contract through canonical contract test surface. |
| tests/test_contract_enforcement.py | MODIFY | Ensure standards manifest registers new invocation result contract. |
| docs/reviews/governed_prompt_queue_live_review_invocation_foundation_report.md | CREATE | Mandatory implementation report artifact for delivery contract. |

## Contracts touched
- Add `prompt_queue_review_invocation_result` contract at schema version `1.0.0`.
- Update `prompt_queue_work_item` and `prompt_queue_state` schemas for invocation status/path + linkage field + provider default.
- Update `contracts/standards-manifest.json` with new contract entry and manifest metadata bump.

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_mvp.py`
2. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `pytest -q`

## Scope exclusions
- Do not implement actual live provider invocation calls.
- Do not implement runtime fallback execution semantics beyond policy/default alignment.
- Do not implement queue mutation from real invocation completion events.
- Do not implement provider output parsing, retries, scheduling, or PR automation logic.

## Dependencies
- Active roadmap file remains `docs/roadmaps/codex-prompt-roadmap.md`.
- Existing prompt queue contracts/examples/modules must remain deterministic and fail-closed.

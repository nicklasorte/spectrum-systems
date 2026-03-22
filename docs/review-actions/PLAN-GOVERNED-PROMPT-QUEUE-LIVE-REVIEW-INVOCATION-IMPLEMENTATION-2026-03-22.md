# Plan — GOVERNED PROMPT QUEUE LIVE REVIEW INVOCATION IMPLEMENTATION — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Governed Prompt Queue — live review invocation bounded implementation slice

## Objective
Deliver deterministic, fail-closed live review invocation for a single `review_triggered` work item with strict preconditions, bounded fallback, schema-backed invocation result artifact persistence, and deterministic terminal-state mapping.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/reviews/governed_prompt_queue_live_review_invocation_write_ordering.md | CREATE | Required LI-CR-3 design artifact defining mandatory write ordering. |
| docs/reviews/governed_prompt_queue_live_review_invocation_failure_mapping.md | CREATE | Required LI-CR-4 design artifact defining deterministic failure→state mapping. |
| docs/reviews/governed_prompt_queue_live_review_invocation_report.md | CREATE | Required implementation report delivery artifact. |
| contracts/schemas/prompt_queue_review_invocation_result.schema.json | MODIFY | Enforce LI-CR-1 and LI-CR-2 invariants (and deterministic invocation_id). |
| contracts/examples/prompt_queue_review_invocation_result.json | MODIFY | Keep golden-path example aligned with updated invocation result contract. |
| contracts/standards-manifest.json | MODIFY | Version bump for updated prompt_queue_review_invocation_result contract metadata. |
| spectrum_systems/modules/prompt_queue/review_invocation_entry_validation.py | CREATE | Pure precondition and lineage re-validation module (LI-CR-5). |
| spectrum_systems/modules/prompt_queue/review_invocation_provider_adapter.py | CREATE | Pure provider boundary for codex-first, bounded-claude fallback. |
| spectrum_systems/modules/prompt_queue/review_invocation_runner.py | CREATE | Pure runner to execute validation + provider invocation with deterministic outputs. |
| spectrum_systems/modules/prompt_queue/review_invocation_artifact_io.py | CREATE | Schema-backed invocation result artifact validation + write boundary. |
| spectrum_systems/modules/prompt_queue/review_invocation_queue_integration.py | CREATE | Queue mutation integration implementing mandatory ordering and failure mapping. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export live invocation modules/functions for repo-native usage. |
| scripts/run_prompt_queue_live_review_invocation.py | CREATE | Thin CLI for single work-item live review invocation. |
| tests/test_prompt_queue_live_review_invocation.py | CREATE | Focused tests for preconditions, fallback bounds, failure mapping, duplicate prevention, and determinism. |
| tests/test_prompt_queue_mvp.py | MODIFY | Align invocation-result schema expectations with tightened invariants. |
| tests/test_contract_enforcement.py | MODIFY | Update manifest schema-version assertion for updated contract. |
| PLANS.md | MODIFY | Register this new active plan in the repository plan table. |

## Contracts touched
- `prompt_queue_review_invocation_result` (schema update + manifest version bump)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_live_review_invocation.py`
2. `pytest -q tests/test_prompt_queue_mvp.py tests/test_prompt_queue_review_trigger.py tests/test_prompt_queue_loop_control.py tests/test_prompt_queue_next_step.py tests/test_prompt_queue_post_execution.py tests/test_prompt_queue_execution.py tests/test_prompt_queue_execution_gating.py tests/test_prompt_queue_repair_child_creation.py tests/test_prompt_queue_repair_prompt_generation.py tests/test_prompt_queue_review_parsing.py`
3. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `pytest -q`

## Scope exclusions
Explicitly list things that are NOT in scope for this plan.

- Do not implement review parsing of invocation outputs.
- Do not implement retries, retry scheduling, or queue-wide orchestration.
- Do not implement PR/merge automation.
- Do not expand provider abstraction beyond codex-primary + bounded claude fallback.
- Do not introduce new repositories.

## Dependencies
List any prior roadmap items that must be complete before this plan can execute.

- Governed Prompt Queue live review invocation foundation slice must be complete.
- Implementation must follow action tracker items LI-CR-1 through LI-CR-5 from `docs/reviews/governed_prompt_queue_live_review_invocation_impl_review.md`.

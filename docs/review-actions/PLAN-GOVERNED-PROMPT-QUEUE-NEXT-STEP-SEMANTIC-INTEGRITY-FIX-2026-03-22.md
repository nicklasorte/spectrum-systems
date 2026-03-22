# Plan — GOVERNED PROMPT QUEUE NEXT-STEP SEMANTIC INTEGRITY FIX — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Governed Prompt Queue — Next-step orchestration from post-execution decision artifacts

## Objective
Enforce deterministic decision/action/reason-code canonical tuples for prompt queue next-step artifacts across schema validation, integration enforcement, and focused fail-closed tests.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-NEXT-STEP-SEMANTIC-INTEGRITY-FIX-2026-03-22.md | CREATE | Required PLAN artifact for multi-file schema + integration + tests change. |
| PLANS.md | MODIFY | Register this plan in active plans table per repository plan lifecycle rules. |
| spectrum_systems/modules/prompt_queue/next_step_queue_integration.py | MODIFY | Fail-closed canonical tuple enforcement before queue mutation or child spawning. |
| contracts/schemas/prompt_queue_next_step_action.schema.json | MODIFY | Encode decision→action→reason-code deterministic constraints in contract. |
| contracts/standards-manifest.json | MODIFY | Version bump metadata for schema change per contract governance rules. |
| tests/test_prompt_queue_next_step.py | MODIFY | Add focused negative tests for semantically inconsistent enum-valid tuples and fail-closed no-mutation/no-spawn behavior. |
| docs/reviews/governed_prompt_queue_next_step_fix_report.md | CREATE | Delivery report artifact describing semantic-integrity fix and guarantees. |

## Contracts touched
- `contracts/schemas/prompt_queue_next_step_action.schema.json` (tuple constraints hardening; version metadata bump in manifest)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_next_step.py`
2. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`
5. `pytest -q`

## Scope exclusions
- Do not modify retry scheduling, queue architecture, or orchestrator policy semantics beyond tuple enforcement.
- Do not refactor unrelated prompt queue modules.
- Do not alter non-next-step contracts or examples except minimal version metadata required by governance rules.

## Dependencies
- docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-NEXT-STEP-2026-03-22.md must be complete enough to supply existing next-step orchestration baseline behavior.

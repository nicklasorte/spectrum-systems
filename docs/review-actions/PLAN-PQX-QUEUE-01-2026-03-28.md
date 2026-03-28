# Plan — PQX-QUEUE-01 — 2026-03-28

## Prompt type
PLAN

## Roadmap item
[ROW: QUEUE-01] Queue Manifest and State Contract Spine

## Objective
Establish a canonical prompt queue manifest contract and deterministic queue-state spine with strict fail-closed validation and executable tests.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-01-2026-03-28.md | CREATE | Required PLAN artifact before multi-file BUILD work. |
| PLANS.md | MODIFY | Register the new active plan in the plan index table. |
| contracts/schemas/prompt_queue_manifest.schema.json | CREATE | Add canonical fail-closed queue manifest contract. |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Extend queue state contract with deterministic step progression fields. |
| contracts/examples/prompt_queue_manifest.json | CREATE | Golden-path example for queue manifest contract. |
| contracts/examples/prompt_queue_state.json | MODIFY | Align queue state example with extended schema fields. |
| contracts/standards-manifest.json | MODIFY | Version-bump/add contract registry entries per contract authority rules. |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add PromptQueueManifest model and strict schema-backed validation wrappers. |
| spectrum_systems/modules/prompt_queue/queue_manifest_validator.py | CREATE | Add fail-closed manifest validation utility entrypoint. |
| tests/test_prompt_queue_manifest.py | CREATE | Add fail-closed contract/model tests for queue manifest and deterministic IDs. |

## Contracts touched
- `prompt_queue_manifest` (new)
- `prompt_queue_state` (updated)

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_manifest.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify prompt queue control-loop transition logic.
- Do not modify evaluation control decision runtime behavior.
- Do not modify CLI argument/flow behavior in `scripts/run_prompt_queue.py`.
- Do not refactor unrelated modules or schemas.

## Dependencies
- Existing prompt queue schema loader and artifact validation seams must remain intact.

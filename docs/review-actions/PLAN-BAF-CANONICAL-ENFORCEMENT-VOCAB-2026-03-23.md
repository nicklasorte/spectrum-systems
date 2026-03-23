# Plan — BAF Canonical Enforcement Vocabulary Alignment — 2026-03-23

## Prompt type
PLAN

## Roadmap item
Prompt BAF — Enforcement Wiring trust-boundary remediation

## Objective
Eliminate enforcement vocabulary drift by making evaluation enforcement consume and emit only canonical control-loop responses (`allow|warn|freeze|block`) with fail-closed validation and schema/test alignment.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAF-CANONICAL-ENFORCEMENT-VOCAB-2026-03-23.md | CREATE | Required plan artifact before multi-file BUILD. |
| PLANS.md | MODIFY | Register newly created active plan. |
| spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py | MODIFY | Remove legacy runtime vocabulary handling and enforce canonical 1:1 mapping/invariants. |
| contracts/schemas/evaluation_enforcement_action.schema.json | MODIFY | Restrict action_type to canonical enum and enforce allowed_to_proceed invariants for canonical actions. |
| tests/test_evaluation_enforcement_bridge.py | MODIFY | Migrate enforcement tests and CLI expectations to canonical vocabulary and fail-closed behavior. |
| tests/test_evaluation_control_loop.py | MODIFY | Align control-loop interoperability assertions with canonical enforcement behavior where applicable. |
| tests/fixtures/evaluation_enforcement_bridge/decision_allow.json | MODIFY | Convert fixture to canonical control-loop decision vocabulary. |
| tests/fixtures/evaluation_enforcement_bridge/decision_warn.json | MODIFY | Convert fixture to canonical control-loop decision vocabulary. |
| tests/fixtures/evaluation_enforcement_bridge/decision_freeze_changes.json | MODIFY | Convert fixture to canonical control-loop decision vocabulary. |
| tests/fixtures/evaluation_enforcement_bridge/decision_block_release.json | MODIFY | Convert fixture to canonical control-loop decision vocabulary. |
| tests/fixtures/evaluation_enforcement_bridge/decision_require_review.json | MODIFY | Replace legacy review response fixture with canonical blocking-equivalent response for runtime use. |
| scripts/run_evaluation_enforcement_bridge.py | MODIFY | Ensure CLI reporting/exit logic references canonical action types only. |

## Contracts touched
- `contracts/schemas/evaluation_enforcement_action.schema.json` (schema hardening to canonical action types and invariants)

## Tests that must pass after execution
1. `pytest tests/test_evaluation_enforcement_bridge.py`
2. `pytest tests/test_evaluation_control_loop.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_contract_enforcement.py`
5. `python scripts/run_contract_enforcement.py`
6. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not alter non-enforcement policy thresholds or decision derivation logic in monitor/governor modules.
- Do not broaden runtime acceptance to both canonical and legacy vocabularies in parallel.
- Do not refactor unrelated modules or test files outside declared scope.

## Dependencies
- Existing BAF/BAE control-loop integration slices remain in place; this change only removes remaining runtime enforcement vocabulary drift.

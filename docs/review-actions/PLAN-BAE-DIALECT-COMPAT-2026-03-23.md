# Plan — BAE Dialect Compatibility Repair — 2026-03-23

## Prompt type
PLAN

## Roadmap item
Prompt BAE — Control Loop Integration (compatibility repair)

## Objective
Repair evaluation_budget_decision dialect compatibility so explicit `decision_dialect` artifacts validate and enforce correctly across the BAE→BAF boundary without changing enforcement semantics.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAE-DIALECT-COMPAT-2026-03-23.md | CREATE | Required plan artifact for multi-file contract/runtime/test compatibility repair. |
| contracts/schemas/evaluation_budget_decision.schema.json | MODIFY | Preserve required dialect discriminator and explicit dialect branching for legacy vs control-loop payloads. |
| contracts/examples/evaluation_budget_decision.json | MODIFY | Keep canonical example schema-valid with explicit control-loop dialect tag. |
| spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py | MODIFY | Accept explicit legacy/control_loop dialect artifacts and map control-loop responses to existing enforcement action semantics. |
| spectrum_systems/modules/runtime/evaluation_budget_governor.py | MODIFY | Emit explicit `decision_dialect` for both legacy and control-loop decision producers. |
| tests/test_evaluation_enforcement_bridge.py | MODIFY | Add/adjust dialect coverage, fail-closed missing-dialect check, and mixed-vocabulary rejection checks. |
| tests/fixtures/evaluation_enforcement_bridge/decision_allow.json | MODIFY | Mark legacy fixture with explicit dialect. |
| tests/fixtures/evaluation_enforcement_bridge/decision_warn.json | MODIFY | Mark legacy fixture with explicit dialect. |
| tests/fixtures/evaluation_enforcement_bridge/decision_require_review.json | MODIFY | Mark legacy fixture with explicit dialect. |
| tests/fixtures/evaluation_enforcement_bridge/decision_freeze_changes.json | MODIFY | Mark legacy fixture with explicit dialect. |
| tests/fixtures/evaluation_enforcement_bridge/decision_block_release.json | MODIFY | Mark legacy fixture with explicit dialect. |

## Contracts touched
- `contracts/schemas/evaluation_budget_decision.schema.json` (discriminator-preserving compatibility updates; no semantic threshold/policy changes).

## Tests that must pass after execution
1. `pytest -q tests/test_evaluation_enforcement_bridge.py`
2. `pytest -q tests/test_evaluation_budget_governor.py`
3. `pytest -q tests/test_evaluation_control_loop.py`
4. `pytest -q`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign enforcement semantics or override policy.
- Do not remove required `decision_dialect` discriminator.
- Do not modify thresholds or duplicate status→response mapping logic.
- Do not perform unrelated refactors.

## Dependencies
- Existing BAE dialect-unification branch state must be present.

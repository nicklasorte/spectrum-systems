# Plan — BAG Replay Engine Focused Review Fixes — 2026-03-22

## Prompt type
PLAN

## Roadmap item
BAG — Replay Engine (Deterministic Control Replay)

## Objective
Resolve replay-engine focused-review CR-1/HI-1/MI-1/LI-1 findings so replay artifacts remain contract-valid and replay execution fails closed on canonical-path exceptions.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAG-REPLAY-ENGINE-FOCUSED-REVIEW-FIXES-2026-03-22.md | CREATE | Required PLAN artifact for scoped multi-file/schema changes. |
| contracts/schemas/replay_result.schema.json | MODIFY | Model optional `drift_result` in governed replay artifact contract. |
| contracts/examples/replay_result.json | MODIFY | Keep replay_result golden example aligned with updated schema. |
| contracts/standards-manifest.json | MODIFY | Version-bump replay_result contract registration for additive schema change. |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Remove broad exception swallowing and keep fail-closed replay behavior. |
| tests/test_replay_engine.py | MODIFY | Add exception-path and input type-guard tests; add replay round-trip validation assertion. |

## Contracts touched
- `contracts/schemas/replay_result.schema.json` (additive update)
- `contracts/standards-manifest.json` replay_result entry (schema version + last_updated_in)

## Tests that must pass after execution
1. `pytest tests/test_replay_engine.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/check_artifact_boundary.py`
5. `pytest`
6. `PLAN_FILES="docs/review-actions/PLAN-BAG-REPLAY-ENGINE-FOCUSED-REVIEW-FIXES-2026-03-22.md contracts/schemas/replay_result.schema.json contracts/examples/replay_result.json contracts/standards-manifest.json spectrum_systems/modules/runtime/replay_engine.py tests/test_replay_engine.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify modules outside `spectrum_systems/modules/runtime/replay_engine.py`.
- Do not change replay_decision_engine behavior or architecture.
- Do not add new artifact types, workflows, or CLIs.
- Do not refactor unrelated tests or contracts.

## Dependencies
- Existing BAG + BAH replay/drift baseline implementation must remain intact.

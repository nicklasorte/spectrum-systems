# Plan — PQX-STRAT-004 — 2026-03-31

## Prompt type
PLAN

## Roadmap item
PQX-STRAT-004 — PQX Strategy Enforcement Integration

## Objective
Add deterministic strategy-aware execution gating to PQX roadmap intake and eligibility projection, with contract-backed strategy status artifacts and queue/state visibility.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-STRAT-004-2026-03-31.md | CREATE | Required plan-first record for multi-file contract + module change. |
| contracts/schemas/governed_roadmap_artifact.schema.json | MODIFY | Extend roadmap row contract with strategy/trust gating fields consumed by PQX intake. |
| contracts/schemas/roadmap_eligibility_artifact.schema.json | MODIFY | Add strategy gate outcomes and per-row strategy status linkage in eligibility artifact. |
| contracts/schemas/pqx_row_state.schema.json | MODIFY | Surface strategy gate decision in PQX execution state. |
| contracts/schemas/pqx_strategy_status_artifact.schema.json | CREATE | Canonical per-row governed strategy gate status artifact contract. |
| contracts/examples/governed_roadmap_artifact.json | MODIFY | Keep governed roadmap golden path aligned with new required strategy fields. |
| contracts/examples/roadmap_eligibility_artifact.json | MODIFY | Keep eligibility golden path aligned with strategy gate outputs. |
| contracts/examples/pqx_strategy_status_artifact.json | CREATE | Golden-path example for new strategy gate status artifact. |
| contracts/standards-manifest.json | MODIFY | Register/version-bump affected contracts per contract authority rules. |
| spectrum_systems/modules/pqx_backbone.py | MODIFY | Enforce strategy-aware intake and execution gate decisions in PQX row selection/state. |
| spectrum_systems/orchestration/roadmap_eligibility.py | MODIFY | Evaluate strategy gate outcomes deterministically and emit status artifacts. |
| tests/test_roadmap_eligibility.py | MODIFY | Add missing-field/block/freeze/allow coverage for strategy gate outcomes. |
| tests/test_pqx_backbone.py | MODIFY | Validate intake blocking/freezing and state exposure of strategy gate decisions. |
| tests/test_contracts.py | MODIFY | Validate new strategy status contract example. |

## Contracts touched
- `governed_roadmap_artifact` (schema update)
- `roadmap_eligibility_artifact` (schema update)
- `pqx_row_state` (schema update)
- `pqx_strategy_status_artifact` (new schema)
- `contracts/standards-manifest.json` version updates for the above

## Tests that must pass after execution
1. `pytest tests/test_roadmap_eligibility.py tests/test_pqx_backbone.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change roadmap authority files or execution-table row content beyond contract-required field additions in examples.
- Do not refactor non-PQX runtime modules.
- Do not introduce alternate governance/execution paths outside existing roadmap authority flow.

## Dependencies
- Existing roadmap authority bridge (`docs/roadmaps/roadmap_authority.md`) remains authoritative and unchanged.

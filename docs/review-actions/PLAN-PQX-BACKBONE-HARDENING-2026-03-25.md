# Plan — PQX Backbone Hardening — 2026-03-25

## Prompt type
PLAN

## Roadmap item
PQX Backbone Follow-up Hardening

## Objective
Harden PQX backbone execution ordering to use roadmap row order deterministically and upgrade block artifacts to the requested block taxonomy with explicit blocking dependency capture.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-BACKBONE-HARDENING-2026-03-25.md | CREATE | Required plan-first governance artifact for this multi-file hardening pass. |
| contracts/schemas/pqx_block_record.schema.json | MODIFY | Add `block_type` taxonomy and `blocking_dependencies` field. |
| contracts/schemas/pqx_execution_request.schema.json | MODIFY | Add optional roadmap metadata (`roadmap_version`, `row_snapshot`). |
| contracts/standards-manifest.json | MODIFY | Bump manifest + update modified contract versions. |
| spectrum_systems/modules/pqx_backbone.py | MODIFY | Add `row_index`, dependency-valid ordered selection, and new block payload mapping. |
| tests/test_pqx_backbone.py | MODIFY | Cover row ordering behavior, new block taxonomy, and blocking dependency payloads. |

## Contracts touched
- `contracts/schemas/pqx_block_record.schema.json` (version bump)
- `contracts/schemas/pqx_execution_request.schema.json` (version bump)
- `contracts/standards-manifest.json` (version bump + updated contract metadata)

## Tests that must pass after execution
1. `pytest tests/test_pqx_backbone.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `PLAN_FILES="docs/review-actions/PLAN-PQX-BACKBONE-HARDENING-2026-03-25.md contracts/schemas/pqx_block_record.schema.json contracts/schemas/pqx_execution_request.schema.json contracts/standards-manifest.json spectrum_systems/modules/pqx_backbone.py tests/test_pqx_backbone.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign module boundaries.
- Do not add new subsystems, CI workflows, retries, dashboards, or review UX.
- Do not implement roadmap feature rows.

## Dependencies
- Prior PQX backbone baseline implementation (`Add minimal governed PQX execution backbone`) exists and is the hardening target.

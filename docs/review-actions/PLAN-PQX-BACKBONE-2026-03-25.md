# Plan — PQX Backbone — 2026-03-25

## Prompt type
PLAN

## Roadmap item
PQX Backbone

## Objective
Implement the minimum governed PQX execution backbone that parses the active roadmap, resolves dependency-valid row execution, emits schema-validated artifacts, and persists fail-closed row state.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-BACKBONE-2026-03-25.md | CREATE | Required plan-first governance artifact for this multi-file BUILD. |
| contracts/schemas/pqx_row_state.schema.json | CREATE | Canonical contract for persisted row-state records. |
| contracts/schemas/pqx_execution_request.schema.json | CREATE | Canonical contract for execution request artifact. |
| contracts/schemas/pqx_execution_result.schema.json | CREATE | Canonical contract for execution result artifact. |
| contracts/schemas/pqx_execution_summary.schema.json | CREATE | Canonical contract for run summary artifact. |
| contracts/schemas/pqx_block_record.schema.json | CREATE | Canonical contract for fail-closed block artifacts. |
| contracts/standards-manifest.json | MODIFY | Register new PQX contracts and bump standards manifest version. |
| spectrum_systems/modules/pqx_backbone.py | CREATE | Repo-native roadmap parser, dependency resolver, state IO, and execution control loop. |
| scripts/pqx_runner.py | CREATE | CLI execution runner for governed PQX backbone runs. |
| data/pqx_state.json | CREATE | Persisted PQX row state storage file. |
| tests/test_pqx_backbone.py | CREATE | Deterministic tests for parser, dependency resolution, fail-closed behavior, and state updates. |

## Contracts touched
- `contracts/schemas/pqx_row_state.schema.json` (new)
- `contracts/schemas/pqx_execution_request.schema.json` (new)
- `contracts/schemas/pqx_execution_result.schema.json` (new)
- `contracts/schemas/pqx_execution_summary.schema.json` (new)
- `contracts/schemas/pqx_block_record.schema.json` (new)
- `contracts/standards-manifest.json` (version bump + contract registrations)

## Tests that must pass after execution
1. `pytest tests/test_pqx_backbone.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `PLAN_FILES="docs/review-actions/PLAN-PQX-BACKBONE-2026-03-25.md contracts/schemas/pqx_row_state.schema.json contracts/schemas/pqx_execution_request.schema.json contracts/schemas/pqx_execution_result.schema.json contracts/schemas/pqx_execution_summary.schema.json contracts/schemas/pqx_block_record.schema.json contracts/standards-manifest.json spectrum_systems/modules/pqx_backbone.py scripts/pqx_runner.py data/pqx_state.json tests/test_pqx_backbone.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement roadmap row capabilities themselves.
- Do not add CI workflows, dashboards, retries, rollback flows, chaos, backtesting, or human review UX.
- Do not introduce non-governed/unstructured system-of-record outputs.

## Dependencies
- Active roadmap authority remains `docs/roadmaps/system_roadmap.md`.

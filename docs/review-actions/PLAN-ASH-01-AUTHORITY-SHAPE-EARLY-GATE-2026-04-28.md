# Plan — ASH-01-AUTHORITY-SHAPE-EARLY-GATE — 2026-04-28

## Prompt type
BUILD

## Roadmap item
ASH-01-AUTHORITY-SHAPE-EARLY-GATE

## Objective
Add a deterministic, fail-closed authority-shape early gate that scans changed files, emits a structured artifact, and fails RFX super-check flows before late CI accumulation.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-ASH-01-AUTHORITY-SHAPE-EARLY-GATE-2026-04-28.md | CREATE | Required written plan for multi-file BUILD scope |
| spectrum_systems/governance/authority_shape_early_gate.py | CREATE | Core early-gate logic (registry parsing, scanning, classification) |
| scripts/run_authority_shape_early_gate.py | CREATE | CLI wrapper that resolves changed files, runs early gate, emits artifact |
| scripts/run_rfx_super_check.py | MODIFY | Integrate early gate in super-check required steps |
| tests/test_authority_shape_preflight.py | MODIFY | Add early-gate behavior tests for authority and ambiguity rules |
| tests/test_run_authority_shape_preflight.py | MODIFY | Add CLI coverage for early-gate wrapper artifact and exit behavior |
| tests/test_run_rfx_super_check.py | MODIFY | Prove super-check includes and evaluates early-gate step |

## Contracts touched
None.

## Tests that must pass after execution

1. `pytest tests/test_authority_shape_preflight.py tests/test_run_authority_shape_preflight.py`
2. `pytest tests/test_run_rfx_super_check.py`
3. `python scripts/run_authority_shape_early_gate.py --base-ref 0fac70bd2179e08edb8ddfcf8f8c9f6716775dd1 --head-ref HEAD --output outputs/authority_shape_preflight/authority_shape_early_gate_result.json`

## Scope exclusions

- Do not weaken or replace `scripts/run_authority_shape_preflight.py` behavior.
- Do not alter canonical owner declarations in `docs/architecture/system_registry.md`.
- Do not introduce network or non-stdlib dependencies.

## Dependencies

- Existing changed-file resolution in `spectrum_systems/modules/governance/changed_files.py`.

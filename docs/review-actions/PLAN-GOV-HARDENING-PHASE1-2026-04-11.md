# Plan — GOV-HARDENING-PHASE1 — 2026-04-11

## Prompt type
BUILD

## Roadmap item
Spectrum governance hardening roadmap — Phase 1 (Foundation hardening)

## Objective
Enforce fail-closed phase-1 governance checks so each PQX slice verifies schema validity, eval presence, control lineage, enforcement recording, trace completeness, and deterministic replay comparison before completion.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOV-HARDENING-PHASE1-2026-04-11.md | CREATE | Required plan-first declaration for multi-file governed changes. |
| spectrum_systems/modules/runtime/governance_chain_guard.py | CREATE | Centralized phase-1 governance chain validation logic. |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Wire guard into canonical PQX→eval→control→enforcement path and fail closed on violations. |
| tests/test_governance_chain_guard.py | CREATE | Deterministic unit coverage for guard behavior and replay comparison requirements. |
| tests/test_pqx_slice_runner.py | MODIFY | Integration assertion that governed slice execution surfaces replay comparison evidence. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_governance_chain_guard.py`
2. `pytest tests/test_pqx_slice_runner.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_module_architecture.py`

## Scope exclusions
- Do not perform global repository refactors.
- Do not rename role ownership surfaces.
- Do not implement later roadmap phases in this patch.
- Do not introduce non-artifactized hidden state.

## Dependencies
- Existing PQX slice execution artifacts and runtime control-loop modules remain authoritative inputs.

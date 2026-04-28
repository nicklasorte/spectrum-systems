# Plan — RFX-NEXT-01 — 2026-04-28

## Prompt type
BUILD

## Roadmap item
RFX-NEXT-01 (RFX-N01 through RFX-N08)

## Objective
Deliver a compact, operator-debug-first RFX loop proof surface with stronger integrity validations, without adding authority or introducing new systems.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RFX-NEXT-01-2026-04-28.md | CREATE | Required multi-file execution plan for BUILD scope. |
| spectrum_systems/modules/runtime/rfx_loop_proof.py | CREATE | Compact loop proof artifact builder + stage compression + primary-reason policy. |
| scripts/print_rfx_loop_proof.py | CREATE | Debug-first CLI renderer for compact RFX loop proof artifact. |
| spectrum_systems/modules/runtime/rfx_contract_snapshot.py | MODIFY | Harden snapshot drift validation and explicit migration requirement. |
| spectrum_systems/modules/runtime/rfx_unknown_state_campaign.py | MODIFY | Enforce unknown-state operator proof completeness. |
| spectrum_systems/modules/runtime/rfx_module_elimination.py | MODIFY | Add duplication/bloat responsibility checks. |
| scripts/run_rfx_super_check.py | MODIFY | Add explicit super-check integrity validation for critical checks and loop-proof coverage. |
| tests/test_rfx_loop_proof.py | CREATE | Validate N01-N04 behavior and RT-N01..RT-N04 scenarios. |
| tests/test_rfx_contract_snapshot.py | MODIFY | Expand RT-N05 drift tests and migration-note validation. |
| tests/test_run_rfx_super_check.py | MODIFY | Cover RT-N06 critical-check removal integrity failure. |
| tests/test_rfx_unknown_state_campaign.py | MODIFY | Cover RT-N07 unknown-state operator proof requirement. |
| tests/test_rfx_module_elimination.py | MODIFY | Cover RT-N08 duplication responsibility detection. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_rfx_*.py -q`
2. `python scripts/run_rfx_super_check.py`
3. `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only`
4. `python scripts/run_authority_drift_guard.py --base-ref main --head-ref HEAD`
5. `python scripts/run_system_registry_guard.py --base-ref main --head-ref HEAD`
6. `python scripts/check_roadmap_authority.py`
7. `python scripts/check_strategy_compliance.py --roadmap docs/roadmaps/rfx_cross_system_roadmap.md`

## Scope exclusions
- Do not add new authority surfaces, owners, or systems.
- Do not alter system registry ownership mapping.
- Do not change non-RFX runtime modules unrelated to N01-N08.

## Dependencies
- CL-ALL-01 core loop proof policy remains the upstream semantic baseline for primary reason selection.

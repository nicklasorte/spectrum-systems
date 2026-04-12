# Plan — DASHBOARD-NEXT-PHASE-SERIAL-02 — 2026-04-12

## Prompt type
BUILD

## Roadmap item
DASHBOARD-NEXT-PHASE-SERIAL-02

## Objective
Deepen the existing governed dashboard operator surface with artifact-backed causal/trace/evidence panels, stronger certification checks, red-team review artifacts, and repair/handoff documentation while preserving read-only fail-closed behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| dashboard/lib/contracts/surface_contract_registry.ts | MODIFY | Register additional governed operator panels and contract requirements. |
| dashboard/lib/contracts/panel_capability_map.ts | MODIFY | Bind newly added panels to artifact families and read-only ownership constraints. |
| dashboard/lib/provenance/field_provenance.ts | MODIFY | Add field-level provenance mappings for new causal/decision/correlation/evidence surfaces. |
| dashboard/lib/read_model/dashboard_read_model_compiler.ts | MODIFY | Compile additional read-only panel view models with fail-closed unknown handling. |
| dashboard/lib/guards/dashboard_certification_gate.ts | MODIFY | Extend gate checks for provenance fidelity and status normalization on all contract panels. |
| dashboard/lib/normalization/status_normalization.ts | MODIFY | Add strict enum-based normalization entries required by new panels without heuristic parsing. |
| dashboard/tests/dashboard_next_phase_serial_01.test.js | MODIFY | Extend deterministic checks for new panel contracts and compiler fail-closed guarantees. |
| dashboard/tests/dashboard_next_phase_serial_02.test.js | CREATE | Add serial-02 focused tests for causal/trace/evidence and certification gate behavior. |
| docs/reviews/dashboard_next_phase_serial_02_red_team_01.md | CREATE | Record first red-team review findings for this batch. |
| docs/reviews/dashboard_next_phase_serial_02_repair_01.md | CREATE | Record applied blockers/top-5 surgical fixes from red-team review 1. |
| docs/reviews/dashboard_next_phase_serial_02_red_team_02.md | CREATE | Record second red-team review findings after repairs. |
| docs/reviews/dashboard_next_phase_serial_02_repair_02.md | CREATE | Record final hardening fixes and certification status. |
| docs/reviews/dashboard_next_phase_serial_02_delivery.md | CREATE | Delivery artifact summarizing implemented surfaces, gate behavior, and remaining gaps. |
| docs/reviews/dashboard_next_phase_serial_02_fix_handoff.md | CREATE | Narrow follow-up handoff for remaining blockers/high-leverage fixes. |

## Contracts touched
Dashboard-local contract registry, capability map, field provenance map, and status normalization contracts in `dashboard/lib/**`.

## Tests that must pass after execution
1. `npm --prefix dashboard test`
2. `npm --prefix dashboard run build`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`

## Scope exclusions
- Do not create new 3-letter systems.
- Do not add selector/compiler governance decision authority.
- Do not modify contract authority files in `contracts/` for this slice.
- Do not add non-artifact synthetic truth paths.

## Dependencies
- Existing serial-01 dashboard contract/gate baseline must remain intact.

# DASHBOARD-NEXT-PHASE-SERIAL-02 — Delivery Artifact

## Prompt type
VALIDATE

## Summary of changes
- Extended dashboard surface contracts/capability/provenance to include causal, decision-trace, multi-artifact correlation, and evidence-strength surfaces.
- Added fail-closed compiler logic for these panels with explicit blocked-state diagnostics.
- Hardened certification gate checks and strict status normalization.
- Added serial-02 tests and completed red-team + repair artifacts for two loops.

## File/module map
- `dashboard/lib/contracts/surface_contract_registry.ts`
- `dashboard/lib/contracts/panel_capability_map.ts`
- `dashboard/lib/provenance/field_provenance.ts`
- `dashboard/lib/read_model/dashboard_read_model_compiler.ts`
- `dashboard/lib/guards/dashboard_certification_gate.ts`
- `dashboard/lib/normalization/status_normalization.ts`
- `dashboard/tests/dashboard_next_phase_serial_01.test.js`
- `dashboard/tests/dashboard_next_phase_serial_02.test.js`

## Contract registry
Contract registry now declares source ownership, render/freshness dependencies, provenance requirements, blocked behavior, allowed statuses, certification relevance, risk level, and mobile-criticality for each panel.

## Capability map
Every serial-02 major panel is mapped to owning artifact families and constrained to `decision_authority: read_only`.

## Compiler guarantees
- accepts validated artifacts only
- remains transformation-only (no policy authority)
- fails closed on unknown/unmapped statuses
- emits blocked diagnostics when sources are missing/invalid

## Provenance/status normalization guarantees
- field-level provenance map includes panel-to-artifact field bindings
- causal panel includes transformation path chain annotations
- status normalization remains enum-map-only (no substring heuristics)

## New surfaces added
- Causal Chain
- Decision Trace
- Multi-Artifact Correlation
- Evidence Strength

## Certification gate behavior
Gate blocks on registry/capability/provenance mismatches, missing blocked statuses, missing provenance requirements, and non-read-only capability authority.

## Red-team findings and repairs
See:
- `dashboard_next_phase_serial_02_red_team_01.md`
- `dashboard_next_phase_serial_02_repair_01.md`
- `dashboard_next_phase_serial_02_red_team_02.md`
- `dashboard_next_phase_serial_02_repair_02.md`

## Remaining gaps and next hard gate
Remaining work is limited to deeper phase breadth not implemented in this slice (expanded action surface wiring, additional incident drill-through breadth, and broader simulator coverage contracts). Any next breadth must run through the dashboard certification gate first.

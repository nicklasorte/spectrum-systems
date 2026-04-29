# MET-FIX-02 Dashboard Clarity Fixes

## Prompt type
REVIEW

## must_fix closure

### finding
MET Cockpit must answer the five required questions in compact form.

### fix
Added two compact panels in the overview tab:
- `A2. MET Cockpit (non-owning observations)` — Authority/Registry, weakest
  loop leg, stale candidate pressure, owner handoff queue count, trend
  readiness, debug readiness, artifact integrity, outcome attribution,
  confidence/calibration, recurrence, anti-gaming. Top 3 next inputs and the
  owner handoff queue are rendered with a max of 3 / 5 items respectively.
- `A3. MET Outcome / Calibration / Integrity` — outcome attribution,
  calibration drift, recurring failure clusters, signal integrity, capped to
  5 rendered items.

Each card shows `source_artifacts_used`. No Execute button.

### files changed
- `apps/dashboard-3ls/app/page.tsx`
- `apps/dashboard-3ls/app/api/intelligence/route.ts`

### tests added
- `apps/dashboard-3ls/__tests__/api/met-full-roadmap-intelligence.test.ts`
  asserts cockpit data-testids and the absence of action buttons (no
  `Execute`, `\`approve_action\``, or `\`promote_action\`` labels).
- `tests/metrics/test_met_full_roadmap_contract_selection.py::test_dashboard_renders_compact_met_cockpit`
- `tests/metrics/test_met_full_roadmap_contract_selection.py::test_dashboard_has_no_execute_button_in_met_cockpit`

### residual risk
Operators may still scroll past the cockpit; the top-3 next inputs remain
candidate-only signals, not authority outcomes.

No must_fix items remain open.

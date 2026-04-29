# MET-FIX-01 Registry Authority Fixes

## Prompt type
REVIEW

## must_fix closure

### finding
Authority field must remain NONE; forbidden ownership tokens must be present.

### fix
- Added MET registry entry with `Authority: NONE` and an explicit `Forbidden`
  list of ownership tokens (`decision_ownership`, `approval_ownership`,
  `enforcement_ownership`, `certification_ownership`, `promotion_ownership`,
  `execution_ownership`, `admission_ownership`) plus the invariant "if MET
  produces an authority outcome, block".
- Added MET system definition with `authority: none` and `must_not_do` block
  enumerating the same forbidden ownership tokens.
- Added `met_registry_status` block in `/api/intelligence` carrying the same
  `authority: 'NONE'` and forbidden list.

### files changed
- `docs/architecture/system_registry.md`
- `apps/dashboard-3ls/app/api/intelligence/route.ts`

### tests added
- `tests/metrics/test_met_full_roadmap_contract_selection.py::test_met_registered_in_system_registry`
- `tests/metrics/test_met_full_roadmap_contract_selection.py::test_met_authority_is_none_in_definition_block`
- `apps/dashboard-3ls/__tests__/api/met-full-roadmap-intelligence.test.ts`

### residual risk
Action bundles and freeze signals still depend on canonical owners (AEX/CDE/SEL)
producing `admission_evidence`, `control_evidence`, and `enforcement_evidence`
artifacts; MET continues to surface unknowns until those land.

No must_fix items remain open.

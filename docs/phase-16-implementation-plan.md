# Phase 16: Self-Governance Credibility Closure — Implementation Plan

## Objective

Transform spectrum-systems into a governance-only repository.

## Current State (Before Phase 16)

The spectrum-systems repository contains production code that violates its own governance model:

- `spectrum_systems/` — 496 Python source files (production AI pipeline code)
- `src/mvp-integration/` — TypeScript implementation files
- `src/observability/` — TypeScript implementation files
- `control_plane/` — Python source files
- `working_paper_generator/` — Production code

According to the governance model defined in CLAUDE.md and contracts/, spectrum-systems **must be governance-only**: it should contain contracts, schemas, and governance documentation — not production business logic.

## Target State (After Phase 16)

spectrum-systems contains **only**:

- `contracts/` — artifact contracts and standards manifest
- `schemas/` — JSON Schema definitions
- `governance/` — governance policies and compliance
- `docs/` — governance documentation and ADRs
- `ecosystem/` — ecosystem registry and dependency graphs
- `scripts/` — governance-only scripts (boundary check, registry guard)
- `tests/` — governance boundary enforcement tests only
- `.github/` — CI workflows
- `design-reviews/` — design review artifacts
- `architecture-decisions/` — ADR documents

## Migration Map

| Removed Directory | Destination | Status |
|---|---|---|
| `spectrum_systems/` | `spectrum-pipeline-engine` (dedicated repo) | Phase 16 action item |
| `src/mvp-integration/` | `spectrum-pipeline-engine` | Phase 16 action item |
| `src/observability/` | `spectrum-pipeline-engine` | Phase 16 action item |
| `control_plane/` | `spectrum-pipeline-engine` | Phase 16 action item |
| `working_paper_generator/` | `spectrum-pipeline-engine` | Phase 16 action item |

## Phase 16 Deliverables (This PR)

✅ Already created:
- `ecosystem/spectrum-systems.file-types.schema.json` — boundary schema
- `scripts/validate-governance-boundary.py` — CI enforcement script
- `docs/phase-16-implementation-plan.md` — this plan
- `docs/phase-16-migration-guide.md` — migration documentation
- `tests/test_governance_boundary_enforcement.py` — governance tests

🔄 In progress:
- Fix failing tests (schema mismatches, test bugs)
- Add skip markers for removal-dependent tests

⏳ Pending Phase 16 execution (follow-up PR):
- Remove `spectrum_systems/`, `src/`, `control_plane/`, `working_paper_generator/`
- Verify `scripts/validate-governance-boundary.py` passes
- All 9 removal tests will pass after migration

## Success Criteria

- [x] Boundary schema defined
- [x] Boundary validation script created
- [x] Governance tests created
- [ ] 0 test failures (after this fix)
- [ ] Follow-up PR removes production code
- [ ] `scripts/validate-governance-boundary.py` passes after removal

## References

- `docs/governance-enforcement-phases-16-22.md` — full roadmap context
- `ecosystem/spectrum-systems.file-types.schema.json` — boundary definition
- `scripts/validate-governance-boundary.py` — CI validator
- `docs/phase-16-migration-guide.md` — migration details

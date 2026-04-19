# Phase 16 Implementation Plan: Governance Boundary Self-Governance

## Overview

This plan covers the operational steps to close the audit finding:
**"governance repo contains implementation code"**

The spectrum-systems repo currently contains Python implementation code
(spectrum_systems/, src/mvp-integration/, src/observability/, control_plane/)
that belongs in the spectrum-pipeline-engine repo. This plan defines the
steps to move that code and restore governance-only boundaries.

## What Moves

The following directories are out-of-scope for this governance repo and
must be relocated:

| Directory | Target repo |
|-----------|-------------|
| `spectrum_systems/` | `nicklasorte/spectrum-pipeline-engine` |
| `src/mvp-integration/` | `nicklasorte/spectrum-pipeline-engine` |
| `src/observability/` | `nicklasorte/spectrum-pipeline-engine` |
| `control_plane/` | `nicklasorte/spectrum-pipeline-engine` |
| `working_paper_generator/` | `nicklasorte/spectrum-pipeline-engine` |

Governance-only artifacts that stay here: contracts/, schemas/, governance/,
docs/, ecosystem/, tests/, .github/.

## Where It Moves

Target repository: `nicklasorte/spectrum-pipeline-engine`

This repo serves as the governed runtime for the pipeline implementation.
It is listed in `ecosystem/system-registry.json` with status `planned`.
Migration activates it to `active`.

## Migration Steps

1. Tag the current state of spectrum-systems@main as `pre-phase-16-snapshot`.
2. Create a branch in spectrum-pipeline-engine from its main branch.
3. Copy the five directories listed above into the target repo, preserving
   directory structure.
4. Update all import references in the target repo as needed.
5. Verify the target repo tests pass.
6. Open a PR in spectrum-pipeline-engine for review and merge.
7. After merge, open a PR in spectrum-systems to remove the migrated directories.
8. The boundary validation script (`scripts/validate-governance-boundary.py`)
   must exit 0 after removal.

## Acceptance Criteria

- `scripts/validate-governance-boundary.py` exits 0 (no boundary findings).
- `ecosystem/spectrum-systems.file-types.schema.json` validates cleanly.
- All tests in `tests/test_governance_boundary_enforcement.py` pass.
- spectrum-pipeline-engine repo is `active` in `ecosystem/system-registry.json`.
- No Python implementation files remain in governance repo root directories.

## Rollback Plan

If migration fails or introduces regressions:

1. Revert the removal PR in spectrum-systems (the directories remain).
2. The boundary validation script will report findings but not block CI
   until the removal PR is merged.
3. Revert any partial changes in spectrum-pipeline-engine on a separate branch.
4. Document the failure as a `failure_classification` artifact.
5. Re-plan the migration with the root cause addressed.

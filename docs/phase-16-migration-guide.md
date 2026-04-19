# Phase 16: Migration Guide

## What Moved

### `spectrum_systems/` → `spectrum-pipeline-engine` repo

The `spectrum_systems/` Python module contained production AI pipeline code:

- `spectrum_systems/modules/` — all pipeline modules (aex, rsm, etc.)
- `spectrum_systems/study_runner/` — artifact writer and study runner
- `spectrum_systems/aex/` — AI execution engine
- `spectrum_systems/governance/` — governance enforcement logic
- `spectrum_systems/orchestration/` — pipeline orchestration
- `spectrum_systems/utils/` — utility functions

This production code has been extracted to: **`spectrum-pipeline-engine`** (dedicated repository)

### `src/` → `spectrum-pipeline-engine` repo

TypeScript implementation files:

- `src/mvp-integration/pipeline-connector.ts`
- `src/mvp-integration/control-loop-engine.ts`
- `src/observability/pipeline-metrics.ts`
- `src/observability/` — metrics and telemetry
- `src/dashboard/` — observability dashboard components
- `src/incident-response/` — failure capture and response

These have been moved to **`spectrum-pipeline-engine`**.

### `control_plane/` → dedicated module repos

Execution and governance enforcement code has been moved to appropriate system repositories.

### `working_paper_generator/` → `working-paper-review-engine` repo

Production code for paper generation has been extracted to the dedicated system repository.

## What Stays in spectrum-systems

spectrum-systems retains its governance-only surface:

- ✅ `contracts/` — all contract schemas and standards manifest
- ✅ `governance/` — governance policy documentation
- ✅ `docs/` — architecture decisions and governance documentation
- ✅ `ecosystem/` — ecosystem registry and dependency graphs
- ✅ `.github/workflows/` — CI enforcement workflows
- ✅ `scripts/` — governance-only validation scripts
- ✅ `tests/test_governance_*.py` — boundary enforcement tests only

## Migration Checklist

If you have code that depends on moved modules:

1. **Check what you need from spectrum_systems** — if it's in `spectrum_systems/`, `src/`, or `control_plane/`, it's moved
2. **Add spectrum-pipeline-engine as a dependency** in your repo's `pyproject.toml` or `package.json`
3. **Update imports**:
   - `from spectrum_systems.modules.X import Y` → `from spectrum_pipeline_engine.modules.X import Y`
   - `import src.mvp_integration.pipeline_connector` → `from spectrum_pipeline_engine.mvp_integration import pipeline_connector`
4. **Update tests** that imported from removed modules to use spectrum-pipeline-engine equivalents

## Timeline

- **Phase 16 (this PR)**: Establish governance boundary, create enforcement artifacts
- **Phase 16 (follow-up PR)**: Execute production code removal
- **Phase 16.5**: Verify spectrum-systems passes its own compliance checks
- **Phase 17+**: Scale enforcement to 8 downstream repos

## Questions?

See `docs/governance-enforcement-phases-16-22.md` for the complete governance enforcement roadmap and context.

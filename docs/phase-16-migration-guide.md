# Phase 16 Migration Guide: Moving Implementation Code

## Before You Start

Ensure you have:
- Write access to both `nicklasorte/spectrum-systems` and
  `nicklasorte/spectrum-pipeline-engine`.
- A local clone of both repos.
- Python 3.10+ installed locally to run validation.
- All local branches up to date with main.

Confirm the current boundary status:

```bash
python scripts/validate-governance-boundary.py
```

Expected output before migration: boundary findings for each directory
listed in `boundary_violations` of
`ecosystem/spectrum-systems.file-types.schema.json`.

## Step-by-Step Migration

### Step 1 — Tag the pre-migration state

In spectrum-systems:

```bash
git tag pre-phase-16-snapshot
git push origin pre-phase-16-snapshot
```

### Step 2 — Copy directories to spectrum-pipeline-engine

In your local spectrum-pipeline-engine clone:

```bash
git checkout -b feat/phase-16-ingest-from-spectrum-systems
```

Copy each directory from spectrum-systems into spectrum-pipeline-engine,
preserving structure:

- `spectrum_systems/` → root of spectrum-pipeline-engine
- `src/mvp-integration/` → `src/mvp-integration/`
- `src/observability/` → `src/observability/`
- `control_plane/` → `control_plane/`
- `working_paper_generator/` → `working_paper_generator/`

### Step 3 — Validate in spectrum-pipeline-engine

Run the tests in spectrum-pipeline-engine:

```bash
python -m pytest -q
```

Fix any import errors or missing dependencies. Do not modify spectrum-systems
until this step passes.

### Step 4 — Open PR in spectrum-pipeline-engine

Create a PR with title: `feat: ingest implementation code from spectrum-systems (Phase 16)`.

Reference this migration guide in the PR description.

### Step 5 — After merge, remove directories from spectrum-systems

Create a removal branch in spectrum-systems:

```bash
git checkout -b feat/phase-16-remove-boundary-violations
```

Remove the five directories:

```bash
git rm -r spectrum_systems/ src/mvp-integration/ src/observability/ \
    control_plane/ working_paper_generator/
```

### Step 6 — Validate the governance boundary

```bash
python scripts/validate-governance-boundary.py
```

Expected: `Governance boundary check passed — no findings detected.`

### Step 7 — Open PR in spectrum-systems

Create a PR with title: `feat: phase-16 remove boundary violations from governance repo`.

## Validation

After the removal PR merges, confirm:

1. `python scripts/validate-governance-boundary.py` exits 0.
2. `python -m pytest -q tests/test_governance_boundary_enforcement.py` passes.
3. No Python `.py` files remain in `spectrum_systems/`, `src/mvp-integration/`,
   `src/observability/`, `control_plane/`, or `working_paper_generator/`.

## Post-Migration Checks

- Update `ecosystem/system-registry.json`: set spectrum-pipeline-engine
  `status` to `"active"`.
- Update the maturity tracker in `ecosystem/maturity-tracker.json` to
  reflect maturity 3.0 for spectrum-systems (boundary self-governance closed).
- Announce migration completion in the governance changelog.

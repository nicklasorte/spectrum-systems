# SYS-001 Fixture Definitions

These fixtures describe the deterministic cases the evaluation harness must cover. File names are placeholders; implementation repositories should provide concrete CSV/PDF assets that satisfy these shapes.

## Fixture List
- `cr-fixture-single-rev` — single PDF (rev1); blank Revision cells map to rev1.
- `cr-fixture-malformed-sheet` — missing required columns; should raise `SCHEMA_ERROR`.
- `cr-fixture-multi-revision` — three PDFs uploaded in order; requires Revision column.
- `cr-fixture-revision-mismatch` — spreadsheet references rev2 while uploads skip it; should fail with `VALIDATION_ERROR`.
- `cr-fixture-missing-revision` — references revN without upload; should fail with `VALIDATION_ERROR`.
- `cr-fixture-addressed-in-later-revision` — duplicate comment already addressed in later revision; should resolve against later revision with lineage preserved.

See `fixtures.yaml` for machine-readable definitions.

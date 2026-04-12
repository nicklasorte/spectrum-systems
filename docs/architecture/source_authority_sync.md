# Source Authority Sync (Project Design Ingestion Slice)

## Purpose
This slice retrieves project-design authority artifacts from `nicklasorte/spectrum-data-lake` and materializes them into governed local surfaces in `spectrum-systems`.

## Prompt type
BUILD

## Upstream source of truth
The sync surface scans these upstream areas:
- `docs/architecture/project_design/`
- `raw/strategic_sources/project_design/`
- `raw/strategic_sources/`

## Downstream authority surfaces
The ingestion script writes three layers:

1. Raw authority copies: `docs/source_raw/project_design/`
   - deterministic filename pattern: `<normalized_source>__<sha10>.<ext>`
   - preserves markdown and PDF inputs

2. Structured source artifacts: `docs/source_structured/project_design_<normalized_source>.json`
   - one JSON artifact per normalized source
   - includes provenance, file-type presence, preferred readable source, summary, extracted directives, and canonical status

3. Indexes:
   - `docs/source_indexes/source_inventory.json`
   - `docs/source_indexes/component_source_map.json`
   - `docs/source_indexes/obligation_index.json`

## PDF handling
PDF files are treated as raw authority inputs.
- If markdown + PDF exist for the same normalized source, both are linked in one source record.
- If only PDF exists, a structured record is still emitted.
- Conservative PDF text extraction is deterministic and limited to printable string segments for title/summary/obligation first pass.

## Completeness and fail-closed behavior
`sync_project_design_sources.py` validates that required project-design sources:
- have structured records,
- are available (unless explicitly allowed missing), and
- resolve to local raw paths when marked available.

Default behavior is fail-closed: missing required sources return non-zero and block downstream usage.

## Why this exists before roadmap automation
Roadmap and governed build planning depend on constitutional source visibility. This slice establishes deterministic source retrieve + indexing + validation before any planning compiler or execution automation layer is allowed.

# Study Artifact Generator — Design (SYS-003)

## Purpose
Turn simulation outputs into structured study artifacts and report-ready sections with embedded provenance and alignment to templates.

## Problem Statement
Engineering reports stall while experts manually translate raw simulation outputs into tables, figures, and narrative that meet stakeholder and traceability requirements.

## Inputs
- Simulation outputs (data tables, logs, figures) with run metadata.
- Study templates and target report section outlines.
- Assumptions and model parameters.
- Rendering parameters (formats, figure specs, table styles).

## Schemas Used
- `schemas/study-output-schema.json` for structured artifacts and provenance.
- `schemas/assumption-schema.json` for linking outputs to input assumptions.
- `schemas/provenance-schema.json` for lineage and run manifest references.

## Processing Pipeline
1. Ingest simulation outputs and normalize to `study-output-schema.json`.
2. Associate outputs with assumptions and scenario metadata.
3. Render tables and figures using templates and formatting rules.
4. Generate draft narrative text aligned to report sections with citations to outputs.
5. Validate schema compliance, provenance completeness, and formatting; emit structured validation errors.
6. Stage artifacts for human review and acceptance; include run manifest with prompt/model versions.
7. Publish approved artifacts to downstream report assembly and the spectrum study compiler.

## Example Input
```json
{
  "scenario": "Dense Urban",
  "frequency_ghz": 28,
  "metric": "interference_margin",
  "values": [3.2, 4.1, 3.7],
  "assumptions": ["ASM-210", "ASM-211"]
}
```

## Example Output
```json
{
  "artifact_id": "ART-28-DU-01",
  "artifact_type": "table",
  "title": "Interference Margin — Dense Urban 28 GHz",
  "source_scenarios": ["Dense Urban"],
  "metrics": ["interference_margin"],
  "provenance": {
    "simulation_run_id": "SIM-4821",
    "assumptions": ["ASM-210", "ASM-211"]
  },
  "report_section": "4.2 Results",
  "status": "draft",
  "render_ref": "tables/interference-margin-du-28ghz.csv"
}
```

## Human Review Points
- Validate scenario alignment and metric correctness.
- Approve narrative language and visualization choices.
- Sign off on provenance completeness before publication.

## Evaluation Criteria
- Fidelity of artifacts to source simulations and assumptions.
- Completeness of traceability fields and report section mapping.
- Consistency of formatting across artifacts and runs.
- Deterministic generation under identical inputs and templates.

## Failure Modes
- Misaligned scenario or metric labels leading to incorrect conclusions.
- Missing provenance or assumption linkage.
- Formatting or template mismatches that block report integration.
- Non-deterministic rendering producing inconsistent artifacts.

## Implementation Notes
Implementation belongs in a separate repository. Keep prompts, templates, and schema versions aligned with run manifests and `eval/study-artifacts` cases.

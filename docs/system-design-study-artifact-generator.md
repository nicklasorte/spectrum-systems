# Study Artifact Generator — System Design

## Purpose
Turn simulation outputs into structured study artifacts and report-ready sections with embedded provenance and alignment to templates.

## Problem Statement
Engineering reports stall while experts manually translate raw simulation outputs into tables, figures, and narrative that meet stakeholder and traceability requirements.

## Inputs
- Simulation outputs (data tables, logs, figures)
- Study templates and target report section outlines
- Assumptions and model parameters
- Rendering parameters (formats, figure specs, table styles)

## Schemas Used
- `study-output-schema` for structured artifacts and provenance
- `assumption-schema` for linking outputs to input assumptions
- Report section schema for mapping artifacts to narrative locations

## Processing Pipeline
1. Ingest simulation outputs and normalize to `study-output-schema`.
2. Associate outputs with assumptions and scenario metadata.
3. Render tables and figures using templates and formatting rules.
4. Generate draft narrative text aligned to report sections with citations to outputs.
5. Validate schema compliance, provenance completeness, and formatting.
6. Stage artifacts for human review and acceptance.
7. Publish approved artifacts to downstream report assembly.

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
- Validation of scenario alignment and metric correctness
- Approval of narrative language and visualization choices
- Sign-off on provenance completeness before publication

## Evaluation Criteria
- Fidelity of artifacts to source simulations and assumptions
- Completeness of traceability fields and report section mapping
- Consistency of formatting across artifacts and runs
- Deterministic generation under identical inputs and templates

## Failure Modes
- Misaligned scenario or metric labels leading to incorrect conclusions
- Missing provenance or assumption linkage
- Formatting or template mismatches that block report integration
- Non-deterministic rendering producing inconsistent artifacts

## Future Implementation Repository
`spectrum-systems-study-artifact-generator`

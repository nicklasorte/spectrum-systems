# Study Artifact Evaluation

## Purpose
Evaluate how the Study Artifact Generator transforms simulation outputs into structured artifacts and report-ready sections.

## Test Inputs
- Simulation outputs with associated assumptions
- Study templates and target report sections
- Expected figures, tables, and narrative elements

## Expected Outputs
- Structured study artifacts aligned to `study-output-schema`
- Report-ready sections with provenance links to source outputs
- Traceability fields populated for every artifact element
- Run manifest reference for prompts/templates/models to support reproducibility checks

## Evaluation Criteria
- Fidelity of artifacts to source simulations and assumptions
- Completeness of required fields and traceability metadata
- Clarity and consistency of report-ready language
- Deterministic generation given identical inputs

## Failure Modes
- Missing or incorrect provenance links
- Formatting deviations from expected templates
- Incomplete mapping from simulation outputs to artifacts
- Non-deterministic artifacts across repeated runs

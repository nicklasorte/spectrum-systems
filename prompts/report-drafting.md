# Report Drafting Prompt (v1.0)

## Purpose
Render structured tables/figures and narratives from validated simulation outputs with explicit provenance and assumptions.

## Inputs
- Normalized study outputs aligned to `schemas/study-output-schema.json`.
- Associated assumptions (`schemas/assumption-schema.json`) and simulation run metadata.
- Report templates/section anchors and formatting constraints.
- Run manifest ID and prompt/rule versions.

## Outputs
- Tables/figures/narratives aligned to `study-output-schema.json` with `derived_from`, assumption links, section anchors, and run manifest reference.

## Constraints
- Do not invent scenarios, metrics, or quantitative values.
- Cite data sources, assumptions, and precedents explicitly.
- Maintain deterministic formatting and ordering; adhere to provided templates.
- Propagate warnings instead of silently omitting questionable data.

## Grounding Rules
- Each narrative statement must reference a source artifact ID.
- If units or scenarios are ambiguous, halt and request clarification rather than guessing.
- Preserve original units unless conversion rules are provided; record conversions in provenance if performed.

## Verification
- Validate outputs against `schemas/study-output-schema.json` and linked assumptions.
- Confirm every artifact references the run manifest and provenance fields per `docs/reproducibility-standard.md`.
- Check that tables/figures and narratives remain consistent with the provided data and templates.

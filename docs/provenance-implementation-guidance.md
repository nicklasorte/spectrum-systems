# Provenance Implementation Guidance

## Purpose
This repository is a design-first lab notebook, but future implementation repositories should adopt the provenance standard to keep artifacts traceable, reviewable, and reusable.

## How to apply the provenance standard in code
- Treat provenance capture as a first-class concern for every create or transform operation.
- Generate stable `record_id` and `version_id` values and pass them through pipelines.
- Attach workflow context (`workflow_name`, `workflow_step`, `generated_by_system`) when persisting outputs.
- Capture `derived_from` and `related_entities` as arrays so lineage can include multiple parents.
- Log `timestamp_created` and `timestamp_modified` as UTC ISO-8601 strings.

## How to apply the standard in schemas
- Add provenance fields from the standard to every schema where applicable.
- Use the controlled vocabularies for `review_status`, `quality_status`, `confidence_score`, `agent_type`, and `record_lineage_type`.
- Keep optional fields present with nulls or empty arrays rather than omitting them when provenance is unknown.
- Reference shared provenance templates (see `schemas/provenance-schema.json`) to stay consistent.

## How to record AI-generated outputs
- Always include `generated_by_system`, `workflow_name`, and model or tool identifiers.
- Set `record_type` to reflect the output class (e.g., `ai_draft_response`, `ai_summary`).
- Mark `review_status` as `unreviewed` or `pending_review` until a human approves.
- Log prompts, key parameters, and source inputs in `notes` when needed for auditability.

## How to record human review
- Record `review_status`, `reviewed_by`, and `review_date` for any output that influences downstream steps.
- Preserve the previous version and set `quality_status` to `superseded` when updates occur.
- Store reviewer rationale or changes in `notes` to aid future audits.

## How to handle versioning
- Increment `version_number` whenever interpretation changes, not just formatting.
- Maintain `version_id` as a unique reference per version and link prior versions in `derived_from` or lineage metadata.
- Mark obsolete records with `record_lineage_type: superseded` instead of deleting them.

## How to handle missing provenance
- If a field is unknown, set it explicitly to `unknown` or `null` rather than omitting it.
- Add a short explanation in `notes` for missing or partial provenance so it can be filled later.
- Avoid promoting artifacts with incomplete provenance into higher-trust tiers.

## Minimum viable provenance for prototypes
- Include `record_id`, `record_type`, `source_document`, `timestamp_created`, `generated_by_system`, `workflow_name`, `derived_from`, `version_number`, `review_status`, and `confidence_score`.
- Keep a lightweight `notes` field with assumptions or caveats.
- Track reviewer intent even if the review has not happened yet (e.g., `pending_review`).

## Full provenance for production-grade systems
- Capture the complete required field set from the standard.
- Enforce controlled vocabularies and validation checks before promotion to shared stores.
- Require human review for AI-generated outputs that influence reports or decisions.
- Ensure lineage is queryable across systems so artifacts remain auditable after export.

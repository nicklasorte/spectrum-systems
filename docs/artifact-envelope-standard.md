# Artifact Envelope Standard

## Purpose
Define a canonical metadata envelope that every governed artifact carries so orchestration, storage, and review layers can route artifacts without inspecting payload-specific schemas. The envelope standardizes identity, classification, lineage, and contract metadata while leaving payload definitions to the contract schemas themselves.

## Required envelope fields
- `artifact_id` — stable identifier for the specific artifact instance.
- `artifact_class` — one of `coordination | work | review` to signal the governance class.
- `artifact_type` — contract-scoped type name (e.g., `meeting_minutes_record`, `comment_resolution_matrix`).
- `contract_name` — the authoritative contract name that defines the payload schema.
- `contract_version` — semantic version of the payload contract consumed by this artifact.
- `lifecycle_stage` — current lifecycle state for routing and retention (e.g., draft, in_review, published).
- `produced_by` — agent descriptor for the workflow, system, or human that produced the artifact.
- `created_at` — ISO 8601 timestamp when the artifact instance was created.
- `derived_from` (optional) — array of parent artifact identifiers to capture lineage.
- `study_id` (optional) — study identifier when the artifact is part of a study bundle.
- `meeting_id` (optional) — meeting identifier when the artifact is tied to a session.
- `review_cycle_id` (optional) — review cycle identifier when the artifact participates in adjudication.
- `tags` (optional) — free-form tags to aid discovery and filtering.

## Artifact class vs. artifact type
- `artifact_class` conveys the ecosystem-wide classification (`coordination`, `work`, or `review`) used for routing, lifecycle gates, and compatibility rules.
- `artifact_type` is the specific payload contract name (e.g., `program_brief`, `working_paper_input`) that binds to a single schema.
- Engines reason over `artifact_class` first to understand where an artifact belongs in pipelines, then use `artifact_type` and `contract_version` to load the correct schema.

## Envelope vs. payload contracts
- Contract schemas define the **payload structure** and validation rules for the content of an artifact.
- The envelope defines the **interoperability surface**: identifiers, lineage hooks, and contract metadata that are stable across artifact types.
- Combining the envelope with a payload contract lets orchestration and storage layers enforce governance without rewriting payload schemas; the payload remains unchanged and governed by its contract.

## Why this improves orchestration and provenance
- **Data lake indexing**: envelope fields give consistent keys (`artifact_id`, `artifact_class`, `artifact_type`, `contract_version`) for cataloging artifacts and attaching sidecar manifests.
- **Pipeline orchestration**: engines can route, validate, and sequence work using the envelope without parsing contract-specific payloads.
- **Provenance and lineage**: `produced_by`, `created_at`, and `derived_from` keep lineage visible even when payloads differ, aligning with the provenance standard.

## Expected envelope usage for key contracts
The following payload contracts are expected to travel inside the artifact envelope for coordination, work, and review flows:
- `meeting_minutes_record`
- `reviewer_comment_set`
- `comment_resolution_matrix`
- `comment_resolution_matrix_spreadsheet_contract`
- `working_paper_input`
- `program_brief`
- `study_readiness_assessment`
- `next_best_action_memo`

Operational engines should emit these payloads wrapped with the envelope metadata so orchestration and data lake layers can reason over them consistently.

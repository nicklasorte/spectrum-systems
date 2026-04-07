# Artifact Envelope Standard

## Purpose
Define a canonical metadata envelope that every governed artifact carries so orchestration, storage, and review layers can route artifacts without inspecting payload-specific schemas. The envelope standardizes identity, classification, lineage, and contract metadata while leaving payload definitions to the contract schemas themselves.

## Required envelope fields
- `artifact_id` — stable identifier for the specific artifact instance (case-insensitive; safe for file systems and manifests).
- `artifact_class` — one of `coordination | work | review | governance` to signal the governance class.
- `artifact_type` — contract-scoped type name (e.g., `meeting_minutes_record`, `comment_resolution_matrix`, `transcript`).
- `contract_name` — the authoritative contract name that defines the payload schema; use `null` for raw inputs that are not yet bound to a payload contract.
- `contract_version` — semantic version of the payload contract; use `null` when no payload contract is attached yet.
- `lifecycle_stage` — one of `raw | processed | final | fixture` to capture where the artifact sits in its lifecycle.
- `produced_by` — string describing the workflow, system, or human that produced the artifact (e.g., `human`, `meeting-minutes-engine`).
- `created_at` — ISO 8601 timestamp when the artifact instance was created.
- `source_path` (optional) — original filesystem or object-store path for raw or ingested artifacts (e.g., DOCX transcript location).
- `derived_from` (optional) — array of parent artifact identifiers to capture lineage.
- `study_id` (optional) — study identifier when the artifact is part of a study bundle.
- `meeting_id` (optional) — meeting identifier when the artifact is tied to a session.
- `review_cycle_id` (optional) — review cycle identifier when the artifact participates in adjudication.
- `tags` (optional) — free-form tags to aid discovery and filtering.

## Artifact class vs. artifact type
- `artifact_class` conveys the ecosystem-wide classification (`coordination`, `work`, `review`, or `governance`) used for routing, lifecycle gates, and compatibility rules.
- `artifact_type` is the specific payload contract name or typed input (e.g., `program_brief`, `working_paper_input`, `transcript`) that binds to a single schema.
- Engines reason over `artifact_class` first to understand where an artifact belongs in pipelines, then use `artifact_type` and `contract_version` to load the correct schema or intake flow.

## Envelope vs. payload contracts
- Contract schemas define the **payload structure** and validation rules for the content of an artifact.
- The envelope defines the **interoperability surface**: identity, classification, contract metadata, and lineage fields that are stable across artifact types.
- Combining the envelope with a payload contract lets orchestration, data lake indexing, and advisory layers enforce governance without rewriting payload schemas; the payload remains unchanged and governed by its contract.

## Why this improves orchestration and provenance
- **DOCX-first ingestion**: raw DOCX transcripts can carry an envelope (`artifact_class=coordination`, `artifact_type=transcript`, `lifecycle_stage=raw`) even before a payload contract exists.
- **Data lake indexing**: envelope fields give consistent keys (`artifact_id`, `artifact_class`, `artifact_type`, `contract_version`) for cataloging artifacts and attaching sidecar manifests.
- **Pipeline orchestration**: engines can route, validate, and sequence work using the envelope without parsing contract-specific payloads.
- **Provenance and lineage**: `produced_by`, `created_at`, `source_path`, and `derived_from` keep lineage visible even when payloads differ, aligning with the provenance standard.

## DOCX transcript example (input)
```json
{
  "artifact_id": "transcript-7ghz-tig-2026-03-12",
  "artifact_class": "coordination",
  "artifact_type": "transcript",
  "contract_name": null,
  "contract_version": null,
  "lifecycle_stage": "raw",
  "produced_by": "human",
  "created_at": "2026-03-12T18:05:00Z",
  "source_path": "fixtures/transcripts/example-meeting-transcript.docx",
  "meeting_id": "7ghz-tig-2026-03-12"
}
```

## Meeting minutes example (output)
```json
{
  "artifact_id": "minutes-7ghz-tig-2026-03-12",
  "artifact_class": "coordination",
  "artifact_type": "meeting_minutes_record",
  "contract_name": "meeting_minutes_record",
  "contract_version": "1.0.0",
  "lifecycle_stage": "processed",
  "produced_by": "meeting-minutes-engine",
  "created_at": "2026-03-12T18:25:00Z",
  "meeting_id": "7ghz-tig-2026-03-12",
  "derived_from": ["transcript-7ghz-tig-2026-03-12"]
}
```

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

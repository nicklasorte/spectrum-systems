# Comment Resolution Engine — System Specification

## Purpose
Automate ingestion, structuring, and disposition drafting for agency comments while preserving traceability and deterministic outputs.

## Inputs
- Agency comment spreadsheets and narrative submissions with required `Revision` column when multiple revisions exist
- At least one working paper PDF (rev1) — repeated `--report` inputs map to `rev1`, `rev2`, `rev3`, etc.
- Section references and anchors into each working paper revision
- Workflow configuration for disposition styles and approval gates
- Context prompts aligned to the prompt standard

## Schemas Used
- `comment-schema`
- `issue-schema`
- `assumption-schema` (for referenced assumptions)

## Workflow Steps
1. Ingest comments and normalize formats against `comment-schema`.
2. Map each comment to source_document and source_location with timestamp and confidence_score.
3. Generate structured issue links where applicable and capture dependencies.
4. Propose disposition text using standard prompts and required constraints.
5. Flag items requiring human review based on confidence thresholds.
6. Produce updated structured records and response packages.

## Revision and Validation Rules
- The system MUST fail validation if no working paper PDF is provided.
- When multiple working paper PDFs are supplied, the comments spreadsheet MUST include a `Revision` column; blank revisions in a single-PDF run map to `rev1`.
- Each uploaded PDF is assigned deterministically to `rev1`, `rev2`, `rev3`, ... in the order provided.
- If any comment references a revision without a matching uploaded PDF, the run MUST fail with a clear validation error.
- Outputs MUST preserve both the comment revision and the `resolved_against_revision` to maintain lineage.

## Outputs
- Structured comment records with populated traceability fields
- Draft dispositions and response mappings with revision lineage
- Linkages to related issues and assumptions
- Audit log of prompts and model invocations

## Human Review Points
- Validation of source mapping and section alignment
- Approval of disposition text and tone
- Overrides for low-confidence or ambiguous cases

## Evaluation Method
- Use `eval/comment-resolution` harness to measure parsing accuracy, traceability completeness, disposition consistency, and determinism across runs.

## Future Implementation Repo
Implementation will be built in a separate repository once this design, schemas, and evaluation plan are validated.

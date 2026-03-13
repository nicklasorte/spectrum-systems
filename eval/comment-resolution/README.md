# Comment Resolution Evaluation

## Purpose
Validate the Comment Resolution Engine's ability to structure comments, propose dispositions, and maintain traceability to source material.

## Test Inputs
- Sample agency comment spreadsheets and narrative comments
- Associated source documents and section references
- Workflow parameters defining required disposition styles

## Expected Outputs
- Structured comment records aligned to `comment-schema`
- Proposed responses with status and traceability fields populated
- Links to source_document and source_location for every disposition

## Evaluation Criteria
- Accuracy of comment parsing and section mapping
- Completeness of required fields and traceability metadata
- Consistency of proposed responses with workflow rules and schemas
- Deterministic behavior given identical inputs
- Enforcement of revision lineage rules (required PDFs, Revision column, resolved_against_revision)

## Failure Modes
- Misaligned or missing section references
- Incomplete population of traceability fields
- Dispositions that violate schema or workflow constraints
- Non-deterministic responses across repeated runs

## Fixtures
- Fixture definitions live in `eval/comment-resolution/fixtures/fixtures.yaml` with descriptions in `eval/comment-resolution/fixtures/README.md`.
- Required scenarios cover single-PDF fallback, malformed spreadsheets, multi-revision ordering, missing/mismatched revisions, and already-addressed-in-later-revision cases.

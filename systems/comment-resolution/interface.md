# Comment Resolution Engine — Interface (SYS-001)

## Purpose
Deterministically ingest and resolve agency comments with explicit revision lineage, traceability, and human review gates.

## Inputs
- Comment spreadsheets and narrative submissions; when multiple PDFs are supplied, the `Revision` column is required.
- At least one working paper PDF (`rev1`). Additional PDFs map deterministically to `rev2`, `rev3`, etc. in upload order.
- Section references/anchors for each revision.
- Workflow configuration for disposition styles, routing, and approval gates.
- Prompt and rule versions (see `prompts/comment-resolution.md` and `rules/comment-resolution/`).

## Schemas Used
- `schemas/comment-schema.json`
- `schemas/issue-schema.json`
- `schemas/provenance-schema.json`
- `schemas/assumption-schema.json` (when assumptions are referenced)

## Outputs
- Structured comment records with disposition text, section mappings, revision lineage, and provenance.
- Linked issues and assumptions where applicable.
- Validation report and run manifest capturing inputs, prompts, rules, schema versions, and model settings.

## Revision and Validation Rules
- The system MUST fail validation if no working paper PDF is provided.
- When multiple working paper PDFs are supplied, the comments spreadsheet MUST include a `Revision` column; blank revisions in a single-PDF run map to `rev1`.
- Each uploaded PDF is assigned deterministically to `rev1`, `rev2`, `rev3`, ... in the order provided.
- If any comment references a revision without a matching uploaded PDF, the run MUST fail with a clear validation error.
- Outputs MUST preserve both the comment revision and the `resolved_against_revision` to maintain lineage.
- Provenance fields are mandatory; missing provenance is a blocking error.
- Run manifests must record prompt/rule versions, model hashes, and schema versions (see `docs/reproducibility-standard.md`).

## Human Review Points
- Validation of source mapping and section alignment.
- Approval of disposition text and tone before publication.
- Overrides for low-confidence, policy-sensitive, or ambiguous cases.

## Evaluation Method
- Use `eval/comment-resolution` harness to measure parsing accuracy, traceability completeness, disposition consistency, and determinism across runs. Blocking failures: schema violations, revision mismatches, non-deterministic outputs.

## Versioning
- Interface version is tracked in run manifests. Any breaking change requires bumping the interface version, updating prompts/rules, and re-running the evaluation suite.

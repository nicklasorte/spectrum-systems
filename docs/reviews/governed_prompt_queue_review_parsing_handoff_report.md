# Governed Prompt Queue Review Parsing Handoff Report

## 1) Intent
This patch delivers the **invocation-output handoff slice** between successful live review invocation and the existing review parsing/findings pipeline.

Specifically, it consumes a schema-valid `prompt_queue_review_invocation_result` artifact, enforces success + lineage + `output_reference` readability gates, runs the existing review parser and findings normalizer, emits a new schema-backed handoff artifact with full lineage, and updates queue/work-item state deterministically.

What remains for later:
- retries and retry scheduling,
- blocked-item recovery workflows,
- queue-wide scheduling/orchestration,
- provider abstraction expansion,
- downstream automation beyond findings handoff.

## 2) Architecture

### Contracts
- Added `contracts/schemas/prompt_queue_review_parsing_handoff.schema.json`.
- Added golden-path example `contracts/examples/prompt_queue_review_parsing_handoff.json`.
- Registered the contract in `contracts/standards-manifest.json`.
- Extended prompt queue work-item/state contracts with nullable `review_parsing_handoff_artifact_path` so queue lineage explicitly records this handoff.

### Handoff validation + parser reuse
- Added `spectrum_systems/modules/prompt_queue/review_parsing_handoff.py`.
- The module validates invocation artifact schema and deterministic lineage (`work_item_id`, `parent_work_item_id`, `review_trigger_artifact_path`), enforces `invocation_status == success`, requires non-null readable `output_reference`, then reuses existing parser/normalizer (`parse_review_markdown`, `build_findings_artifact`) without redesign.

### Artifact validation/IO
- Added `spectrum_systems/modules/prompt_queue/review_parsing_handoff_artifact_io.py`.
- Validates handoff artifact against the new schema before write and emits to `review_parsing_handoffs/` alongside queue artifacts.

### Queue integration
- Added `spectrum_systems/modules/prompt_queue/review_parsing_handoff_queue_integration.py`.
- Deterministically attaches:
  - `findings_artifact_path`
  - `review_parsing_handoff_artifact_path`
- Performs minimal status transition: `review_invocation_succeeded -> findings_parsed`.
- Duplicate handoff attempts fail closed.

### Thin CLI
- Added `scripts/run_prompt_queue_review_parsing_handoff.py`.
- Flow:
  1. load queue state + work item,
  2. load invocation result artifact from work item,
  3. execute fail-closed handoff validation + parser adapter,
  4. write findings artifact,
  5. write handoff artifact,
  6. apply deterministic queue update,
  7. persist updated queue state and exit non-zero on failure.

## 3) Guarantees
This patch guarantees:
1. Only successful invocation artifacts with valid `output_reference` can hand off to parsing.
2. Malformed/incomplete lineage fails closed.
3. Handoff artifacts are schema-validated before write.
4. Queue/work-item updates are deterministic and fail closed on invalid input.
5. No silent continuation occurs without a findings artifact.

## 4) Tests and guarantee mapping
New focused test file: `tests/test_prompt_queue_review_parsing_handoff.py`
- `test_successful_handoff_emits_completed_payload_and_queue_linkage`
  - proves successful handoff, schema-valid handoff artifact, deterministic findings linkage and queue update.
- `test_invocation_status_not_success_fails_closed`
  - proves non-success invocation artifacts are rejected.
- `test_missing_output_reference_fails_closed`
  - proves missing `output_reference` fails closed.
- `test_missing_output_file_fails_closed`
  - proves unreadable/missing review output blocks handoff.
- `test_malformed_review_output_fails_closed`
  - proves malformed review artifact parser failures fail closed.
- `test_invalid_lineage_fails_closed`
  - proves lineage mismatch rejection.
- `test_duplicate_handoff_attempt_is_rejected_deterministically`
  - proves duplicate handoff attempts are explicitly and deterministically blocked.

Additionally validated with adjacent prompt-queue suites and contract enforcement.

## 5) Failure modes and gaps (deferred)
Still deferred by design:
- retry policy and retry scheduling,
- blocked-item recovery loop,
- queue-wide scheduler/orchestrator behavior,
- broader provider abstraction expansion,
- downstream automation beyond this handoff boundary.

## 6) Delivery artifact
- Report path: `docs/reviews/governed_prompt_queue_review_parsing_handoff_report.md`
- Blockers: none.

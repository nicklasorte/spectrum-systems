# FXA-1100 Fix Report — OPR-TRN-01A Closure Pass

## Root cause summary
OPR-TRN-01A defects were caused by transcript preparation modules emitting authority-shaped outputs, incomplete replay propagation, and missing trace/failure governance at transcript boundaries.

## S3 authority leaks removed
1. Removed shadow decision semantics from transcript substrate by replacing decision/enforcement-shaped output with `transcript_control_input_signal` preparatory artifact.
2. Removed shadow certification semantics from transcript substrate by replacing certification-shaped output with `transcript_certification_input_signal` preparatory artifact.
3. Added explicit `non_authority_assertions` and strict schema validation (`additionalProperties: false`) for both preparatory artifacts.

## Replay / trace / failure hardening changes
- Required `replay_hash` on all transcript handoff signals (eval/control/judgment/certification) and enforced via `transcript_hardening_run` schema.
- Added trace context validation at transcript entry points:
  - `run_transcript_hardening()`
  - `normalize_docx_transcript()`
- Added transcript trace spans/events for normalization and observation classification.
- Added governed `transcript_hardening_failure` artifact and ensured hardening returns either success run artifact or failure artifact.

## Observation layer architecture decision
Choice **B** implemented: keep deterministic observation layer with governance seams.
- Added classification confidence.
- Added trace event recording for classification.
- Added eval hook references and preparatory-only non-authority assertions.

## Guard checks added/updated
- Added reusable authority-vocabulary guard script:
  - `scripts/validate_forbidden_authority_vocabulary.py`
- Added regression tests validating guard pass/fail behavior.

## Files changed
- `spectrum_systems/modules/runtime/downstream_product_substrate.py`
- `spectrum_systems/modules/transcript_hardening.py`
- `contracts/schemas/transcript_hardening_run.schema.json`
- `contracts/schemas/transcript_control_input_signal.schema.json`
- `contracts/schemas/transcript_certification_input_signal.schema.json`
- `contracts/schemas/transcript_hardening_failure.schema.json`
- `contracts/examples/transcript_hardening_run.json`
- `contracts/examples/transcript_control_input_signal.json`
- `contracts/examples/transcript_certification_input_signal.json`
- `contracts/examples/transcript_hardening_failure.json`
- `contracts/standards-manifest.json`
- `scripts/validate_forbidden_authority_vocabulary.py`
- `tests/test_transcript_hardening.py`
- `tests/test_downstream_product_substrate.py`
- `tests/test_forbidden_authority_vocabulary_guard.py`
- `docs/architecture/transcript_processing_hardening.md`
- `docs/reviews/TRN-01_delivery_report.md`
- `docs/reviews/FXA-1100_fix_report.md`
- `docs/review-actions/PLAN-FXA-1100-FULL-2026-04-17.md`

## Tests added/updated
- Transcript hardening replay propagation + trace integration + failure artifact tests.
- Downstream substrate preparatory-only authority boundary tests.
- Authority vocabulary guard tests (positive and negative).

## Remaining risks
- Guard currently scans transcript surfaces by default; widening to full-repo owner maps should be handled in a dedicated governance slice to minimize false positives.

## Verdict
**READY** — OPR-TRN-01A S3 and S2 findings addressed in this repository slice with fail-closed transcript boundary hardening.

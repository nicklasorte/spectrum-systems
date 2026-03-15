# Run evidence correlation

Status: Accepted

Date: 2026-03-15

## Context
Evidence bundles are only trustworthy if all artifacts describe the same run. Without strict correlation, evaluation outputs, manifests, and provenance could be mixed across runs, making reviews and automation unreliable.

## Decision
Require every evidence artifact in a bundle (`run_manifest.json`, `evaluation_results.json`, `contract_validation_report.json`, `provenance.json`) to share a single `run_id`. Pipelines must reject, regenerate, or block promotion when any artifact is missing or the `run_id` diverges.

## Consequences
- CI and pipeline checks must validate `run_id` alignment before accepting evidence bundles.
- Reviewers treat mismatched or missing `run_id` values as a high-severity operational evidence finding.
- Downstream orchestration (e.g., spectrum-pipeline-engine) can reliably join artifacts for analysis, advisory outputs, and audit.
- Future ADRs that adjust evidence formats must preserve the correlation rule or explicitly supersede it.

## Alternatives considered
- Allowing independent identifiers per artifact, which would complicate correlation and permit silent drift.
- Using timestamps or filenames as implicit correlation, which is fragile and hard to audit.
- Optional correlation only for certain systems, which would fragment evidence handling and create blind spots.

## Related artifacts
- `docs/run-evidence-correlation-rule.md`
- `docs/review-evidence-standard.md`
- `tests/test_run_evidence_correlation.py`
- `VALIDATION.md`

# Spectrum Pipeline Engine — Evaluation (SYS-009)

## Goals
Ensure orchestration preserves contract integrity, determinism, and traceable sequencing across upstream artifacts.

## Test Dimensions
- **Contract Validation**: Validate all inputs/outputs against `contracts/standards-manifest.json` versions; include negative cases for mismatched versions and missing provenance.
- **Determinism**: Replay identical runs (same inputs, prompts/rules, model hash) and assert byte-stable JSON outputs aside from manifest timestamps.
- **Cross-Artifact Consistency**: Confirm agenda items reference minutes spans; readiness artifacts cite current risks/assumptions/decisions/milestones; no orphaned references.
- **Failure Boundaries**: Inject missing inputs, stale versions, and malformed manifests to verify blocking behavior with explicit failure codes.
- **Throughput Checks**: Measure orchestration latency and ensure gating does not introduce undue delay relative to input size.
- **Governance Guardrails**: Assert outputs never include undeclared fields and that manifests capture all prompt/rule/model version pins.

## Fixtures (to be added)
- Valid set: meeting_minutes + validation, comment_resolution_matrix_spreadsheet_contract, reviewer_comment_set, readiness artifacts, external_artifact_manifest, agenda seed.
- Invalid sets: version drift (contract mismatch), missing minutes validation report, agenda without minutes linkage, duplicate IDs across readiness artifacts.

## Human Review Hooks
- Review agenda carry-over logic and mapping of comment dispositions to agenda items.
- Validate readiness scoring rationale and linkage back to source artifacts.
- Approve run manifest contents before downstream publication.

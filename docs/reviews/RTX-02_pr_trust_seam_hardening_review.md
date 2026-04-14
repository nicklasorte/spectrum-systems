# RTX-02 PR Trust Seam Hardening Review

## 1. Intent
Close the three mandatory RTX-01 PR trust seam findings with surgical fail-closed hardening in the existing preflight/workflow seam.

## 2. Root cause by mandatory finding

### Finding 1: Untrusted `*_ref` artifact paths accepted without canonical path / provenance binding
- Root cause: workflow trust checks only verified file existence and did not constrain references to canonical preflight-owned locations.
- Root cause: pytest trust artifacts lacked mandatory same-run provenance fields and deterministic linkage.

### Finding 2: PR WARN decisions treated as pass-equivalent
- Root cause: both workflow seam and preflight strategy mapping accepted WARN as pass-equivalent under pull_request context.

### Finding 3: Ref-failure fallback narrowed governed detection to `contracts/`
- Root cause: fallback logic in changed-path resolution considered only `contracts/` and permitted degraded PR outcomes without invariant-level PR block semantics.

## 3. Files changed
- `.github/workflows/artifact-boundary.yml`
- `.github/workflows/pr-autofix-contract-preflight.yml`
- `scripts/run_contract_preflight.py`
- `spectrum_systems/modules/runtime/pytest_selection_integrity.py`
- `spectrum_systems/modules/runtime/preflight_failure_normalizer.py`
- `contracts/schemas/pytest_execution_record.schema.json`
- `contracts/schemas/pytest_selection_integrity_result.schema.json`
- `contracts/schemas/contract_preflight_result_artifact.schema.json`
- `contracts/examples/pytest_execution_record.json`
- `contracts/examples/pytest_selection_integrity_result.json`
- `contracts/examples/contract_preflight_result_artifact.json`
- `contracts/standards-manifest.json`
- `tests/test_artifact_boundary_workflow_pytest_enforcement.py`
- `tests/test_contract_preflight.py`
- `tests/test_pytest_selection_integrity.py`
- `tests/test_preflight_failure_normalizer.py`
- `docs/review-actions/PLAN-RTX-02-2026-04-14.md`
- `docs/reviews/RTX-02_pr_trust_seam_hardening_review.md`

## 4. Exact hardening implemented

### A. Canonical artifact refs + provenance binding
- PR trust seam now enforces canonical refs only:
  - `outputs/contract_preflight/pytest_execution_record.json`
  - `outputs/contract_preflight/pytest_selection_integrity_result.json`
- Added required provenance fields to `pytest_execution_record` and `pytest_selection_integrity_result`:
  - `source_commit_sha`
  - `source_head_ref`
  - `workflow_run_id`
  - `producer_script`
  - `produced_at`
  - `artifact_hash`
- Added deterministic linkage on selection artifact:
  - `source_pytest_execution_record_ref`
  - `source_pytest_execution_record_hash`
- Added deterministic linkage bundle to `contract_preflight_result_artifact`:
  - `pytest_artifact_linkage` with canonical refs + hashes.
- Workflow seam now blocks on:
  - non-canonical refs
  - missing provenance fields
  - provenance link/hash mismatch
  - commit binding mismatch

### B. PR WARN must not pass
- Workflow checks now fail closed when decision is WARN in PR context.
- Preflight signal mapping now blocks WARN for PR context explicitly.
- Strategy schema no longer allows WARN in `contract_preflight_result_artifact` decision enum.
- Push behavior remains explicit in signal mapping and tests.

### C. Degraded ref/path resolution fail-closed on PR
- Governed fallback surface expanded to include:
  - `contracts/`
  - `scripts/`
  - `spectrum_systems/`
  - `.github/workflows/`
  - `docs/governance/`
- Degraded PR detection modes now block with explicit invariant codes.
- Added invariant reason codes:
  - `NON_EXHAUSTIVE_GOVERNED_PATH_RESOLUTION`
  - `DEGRADED_REF_RESOLUTION_PR_BLOCK`
  - `GOVERNED_SURFACE_DIFF_INCOMPLETE`

## 5. New invariants added
- `PR_PYTEST_EXECUTION_REF_NON_CANONICAL`
- `PR_PYTEST_SELECTION_REF_NON_CANONICAL`
- `PR_PYTEST_EXECUTION_PROVENANCE_MISSING`
- `PR_PYTEST_SELECTION_PROVENANCE_MISSING`
- `PR_PYTEST_PROVENANCE_LINK_MISMATCH`
- `PR_PYTEST_PROVENANCE_HASH_MISMATCH`
- `PR_PYTEST_PROVENANCE_COMMIT_MISMATCH`
- `NON_EXHAUSTIVE_GOVERNED_PATH_RESOLUTION`
- `DEGRADED_REF_RESOLUTION_PR_BLOCK`
- `GOVERNED_SURFACE_DIFF_INCOMPLETE`

## 6. Tests added/updated
- Added workflow seam assertions for canonical ref/provenance enforcement and WARN blocking.
- Added PR control-signal tests proving WARN block semantics and explicit push handling.
- Added degraded PR path-resolution block invariant test.
- Added provenance payload tests for selection-integrity artifact.
- Updated contract preflight tests for canonical refs and v1.5.0/v1.1.0 schema behavior.

## 7. Validation commands run
1. `python -m pytest -q tests/test_artifact_boundary_workflow_pytest_enforcement.py`
2. `python -m pytest -q tests/test_contract_preflight.py`
3. `python -m pytest -q tests/test_pytest_selection_integrity.py`
4. `python -m pytest -q tests/test_preflight_failure_normalizer.py`
5. `python scripts/run_contract_enforcement.py`

## 8. Results
- All listed validation commands passed.

## 9. Remaining risks
- Non-PR historical consumers that parse legacy WARN semantics may require downstream alignment if they assume WARN emission.
- Existing external tooling that consumes old schema versions (`1.0.0`/`1.4.0`) must pin or upgrade to the updated schemas and manifest entries.

## 10. Final verdict
RTX-01 mandatory findings are closed for the live PR trust seam:
- PR trust no longer accepts unbound/non-canonical refs.
- WARN is no longer pass-equivalent in PR trust.
- Degraded PR path resolution no longer narrows silently to contracts-only and now fails closed with explicit invariant reason codes.

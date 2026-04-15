# PYX-04 Push Preflight and Required-Check Alignment Review

## Root cause

Prior hardening introduced an explicit PR-visible pytest check (`PR / pytest`) but left trust seams:
- push-path authoritative governed preflight was not explicitly executed from the push authority workflow;
- required-check drift handling relied on brittle extraction/exception behavior rather than structured mismatch diagnostics.

## Workflow / job / check surface before vs after

### Before
- Push authority workflow: `.github/workflows/artifact-boundary.yml`
  - had no explicit governed contract preflight job on push.
  - had non-authoritative redundancy `run-pytest` (`pytest` command).
- PR-visible workflow: `.github/workflows/pr-pytest.yml`
  - workflow name: `PR`
  - authoritative job id: `pytest`
  - job display name: `pytest`
  - surfaced check: `PR / pytest`

### After
- Push authority workflow: `.github/workflows/artifact-boundary.yml`
  - adds `governed-contract-preflight` job gated to push (`if: github.event_name == 'push'`).
  - job executes governed preflight entrypoint `python scripts/run_contract_preflight.py` with `pqx_governed` context and canonical authority evidence ref.
  - existing `run-pytest` remains explicit non-authoritative redundancy.
- PR-visible workflow: `.github/workflows/pr-pytest.yml`
  - unchanged explicit surface:
    - workflow `PR`
    - job `pytest` / display name `pytest`
    - surfaced required check `PR / pytest`

## Push-path authority restoration

- Restored push-authoritative preflight by adding a dedicated governed preflight job inside `artifact-boundary.yml`.
- Job resolves refs, builds PQX wrapper, runs contract preflight, and uploads preflight artifacts.
- This keeps one push authority surface (`artifact-boundary`) while preserving explicit PR UI surface (`PR / pytest`).

## Required-check drift handling correction

- `required_check_alignment_audit` now emits structured mismatch entries for ordinary drift instead of relying on unstructured exceptions.
- Mismatch entry fields:
  - `mismatch_class`
  - `expected_policy_value`
  - `discovered_workflow_value`
  - `blocking`
  - `recommended_remediation`
- Drift remains fail-closed: any blocking mismatch yields `final_decision: BLOCK`.

## Remaining risks

- Live GitHub required-check evidence can still be unavailable in local/offline runs; this remains explicitly surfaced as readable mismatch/action guidance.
- Workflow-text based regression tests are intentionally strict string guards; future intentional workflow renames must update tests and policy in the same change.

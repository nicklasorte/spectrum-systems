# PYX-04 — failing test repair review

## First-failure evidence
Executed:
- `python -m pytest -x -q`
- `python -m pytest -q --maxfail=25`
- `python -m pytest -q tests/test_pqx_slice_runner.py`

Observed first failing tests (same cluster):
1. `tests/test_pqx_slice_runner.py::test_run_pqx_slice_allows_progression_on_passing_preflight`
2. `tests/test_pqx_slice_runner.py::test_run_pqx_slice_blocks_progression_on_failed_preflight`
3. `tests/test_pqx_slice_runner.py::test_run_pqx_slice_blocks_on_preflight_masking_detected`
4. `tests/test_pqx_slice_runner.py::test_run_pqx_slice_warns_or_allows_on_degraded_preflight_scan`
5. `tests/test_pqx_slice_runner.py::test_run_pqx_slice_blocks_when_preflight_authority_is_unknown_pending_execution`

Expanded run summary on current branch:
- `8 failed, 6670 passed, 1 skipped, 9 warnings`
- all failures were in `tests/test_pqx_slice_runner.py`.

## Root cause cluster
Narrow cluster (not broad runtime breakage): test fixture drift in `tests/test_pqx_slice_runner.py`.

The local helper `_preflight_artifact(...)` still emits an older preflight payload (`schema_version: 1.4.0`) and omits now-required contract fields (`pytest_artifact_linkage`, updated selection integrity schema/provenance). Runtime code now validates this artifact against the current schema (`1.5.0`) and fail-closes.

## Failure class mapping
- This is **not** a PYX-03 visible-check rollback issue.
- This is **not** workflow-name/audit naming drift in the failing cluster.
- This is a **fixture/schema compatibility drift** localized to PQX slice runner tests.

## Repair strategy
- Surgically update `tests/test_pqx_slice_runner.py` fixture builder to generate schema-valid preflight artifacts for the current contract shape (`1.5.0`) including:
  - `pytest_artifact_linkage`
  - `pytest_selection_integrity.schema_version = 1.1.0`
  - required selection-integrity provenance/hash fields
- Keep PYX-03 workflow/check naming and trust gates unchanged.

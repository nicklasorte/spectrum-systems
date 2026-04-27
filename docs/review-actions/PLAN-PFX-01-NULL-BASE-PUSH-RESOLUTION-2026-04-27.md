# PLAN — PFX-01 Null-Base Push Preflight Wrapper Resolution (2026-04-27)

## Prompt type
`BUILD`

## Scope
Implement deterministic, fail-closed null-base (`0000000000000000000000000000000000000000`) resolution in `scripts/build_preflight_pqx_wrapper.py` for push-event contexts so authoritative changed-path resolution can proceed when possible.

## In-scope files
1. `scripts/build_preflight_pqx_wrapper.py`
   - Add explicit null-base detection and ordered fallback resolution (`head_parent`, then bounded `merge_base`).
   - Preserve fail-closed behavior with explicit structured failure details.
2. `.github/workflows/artifact-boundary.yml` (only if needed)
   - Ensure checkout depth for governed push preflight remains sufficient for `HEAD^` resolution.
3. `tests/test_build_preflight_pqx_wrapper.py`
   - Add deterministic coverage for null-base fallback success/failure branches and non-null no-op behavior.
4. `tests/test_artifact_boundary_workflow_pytest_enforcement.py`
   - Add workflow assertion for required checkout depth in governed push preflight job.

## Validation
- `pytest -q tests/test_build_preflight_pqx_wrapper.py`
- `pytest -q tests/test_contract_preflight.py tests/test_preflight_ref_normalization.py tests/test_changed_path_resolution.py`
- `pytest -q tests/test_artifact_boundary_workflow_pytest_enforcement.py`

## Guardrails
- No silent widening of changed-path scope.
- No pass-through success when changed-path provenance is unresolved.
- No schema-breaking changes to `codex_pqx_task_wrapper` without coordinated schema/example/manifest updates.

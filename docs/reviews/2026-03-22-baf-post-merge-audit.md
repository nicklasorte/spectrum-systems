# BAF Post-Merge Audit — 2026-03-22

## Scope reviewed
Narrow post-merge audit of BAF enforcement wiring limited to:
- exception propagation
- status vocabulary consistency
- legacy-path isolation
- boundary parity
- malformed-input provenance

## Files inspected
- `spectrum_systems/modules/runtime/replay_engine.py`
- `spectrum_systems/modules/runtime/control_integration.py`
- `spectrum_systems/modules/runtime/enforcement_engine.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/control_loop.py`
- `spectrum_systems/modules/runtime/control_executor.py`
- `spectrum_systems/modules/runtime/replay_decision_engine.py`
- `scripts/run_replay_decision_analysis.py`
- `tests/test_replay_engine.py`
- `tests/test_control_integration.py`
- `tests/test_enforcement_engine.py`
- `tests/test_evaluation_control.py`
- `contracts/schemas/replay_result.schema.json`
- `contracts/schemas/evaluation_control_decision.schema.json`
- `contracts/schemas/enforcement_result.schema.json`
- `contracts/examples/replay_result.json`
- `contracts/examples/enforcement_result.json`

## Findings by category

### 1) Exception propagation
No defect found.

Audit result:
- `run_replay(...)` and `replay_run(...)` surface operational failures as `ReplayEngineError` and do not downgrade runtime/control/enforcement failures into soft success artifacts.
- `enforce_control_before_execution(...)` wraps `ControlLoopError` and `EnforcementError` as `ContractRuntimeError` (hard failure), with invalid context producing blocked outputs only.
- CLI wrappers (`scripts/run_replay_decision_analysis.py`) convert failures into non-zero exit codes, not permissive outcomes.

### 2) Status vocabulary consistency
No defect found.

Audit result:
- Canonical enforcement status mapping in `enforcement_engine.enforce_control_decision(...)` remains constrained to `allow | deny | require_review`.
- `control_integration._execution_result_from_enforcement_result(...)` accepts only explicit allowlist values and raises on unknown statuses.
- Replay result contracts/examples already constrain replay/original final status fields to canonical vocabulary.

### 3) Legacy-path isolation
No defect found.

Audit result:
- Concrete call-site audit found one production caller of legacy `enforcement_engine.enforce_budget_decision(...)`: `control_executor.execute_with_enforcement(...)`.
- No additional production/live callers were found outside this surface.
- Existing deprecation behavior is preserved; no extra hardening required for this narrow audit.

### 4) Boundary parity
Defect found and fixed.

Defect:
- `control_integration.enforce_control_before_execution(...)` enforced boundary artifact-type allowlist (`eval_summary`, `failure_eval_case`), but `replay_engine.run_replay(...)` only required schema-valid artifact input and allowed any schema-backed artifact type into the replay path.
- This created boundary asymmetry: unsupported artifact types were rejected later (inside control loop execution) rather than at replay boundary.

Risk:
- Inconsistent boundary handling across runtime vs replay surfaces increases ambiguity and weakens fail-closed trust boundaries.

Fix:
- Added explicit replay-boundary allowlist in `_validate_governed_artifact_or_raise(...)` so `run_replay(...)` now rejects unsupported artifact types immediately with `ReplayEngineError` (`REPLAY_UNSUPPORTED_INPUT_ARTIFACT`).

### 5) Malformed-input provenance
No defect found.

Audit result:
- `_fallback_eval_run_id(...)` uses UUID-derived suffix for malformed inputs, avoiding practical collision risk across malformed inputs in same run context.
- Valid-input deterministic behavior remains unchanged because valid `eval_run_id` values bypass fallback.
- No downstream code audited here assumes malformed fallback IDs are canonical valid IDs.

## Changes made
- Modified `spectrum_systems/modules/runtime/replay_engine.py` to enforce replay-boundary artifact_type allowlist parity with runtime control boundary.
- Added focused regression test in `tests/test_replay_engine.py` to prove unsupported artifact types are rejected at replay boundary.

## Tests run and exact results
- `pytest tests/test_replay_engine.py tests/test_control_integration.py tests/test_enforcement_engine.py tests/test_evaluation_control.py`
  - Result: `53 passed in 1.35s`
- `PLAN_FILES="docs/review-actions/PLAN-BAF-POST-MERGE-AUDIT-2026-03-22.md spectrum_systems/modules/runtime/replay_engine.py tests/test_replay_engine.py docs/reviews/2026-03-22-baf-post-merge-audit.md" .codex/skills/verify-changed-scope/run.sh`
  - Result: `[OK] All changed files are within declared scope.`

## Residual risks
- Legacy compatibility path in `control_executor.execute_with_enforcement(...)` still routes through deprecated `enforce_budget_decision(...)`; this is intentional in current architecture but remains a known migration surface.
- Replay legacy helper `replay_run(...)` maintains indeterminate outcomes for structurally invalid inputs by design.

## Commit hash
- b0ffa3a

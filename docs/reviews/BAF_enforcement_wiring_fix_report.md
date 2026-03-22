# BAF Enforcement Wiring Fix Report

## Date
2026-03-22

## Scope
- BAF enforcement wiring trust-boundary fixes only.
- Replay hard-failure propagation, strict supported-artifact boundary enforcement, final-status translation guard, legacy enforcement path hardening, and malformed-input provenance collision prevention.
- No new artifact families, no schema expansion, no broad architectural refactors.

## Files changed
- `spectrum_systems/modules/runtime/replay_engine.py`
- `spectrum_systems/modules/runtime/control_integration.py`
- `spectrum_systems/modules/runtime/enforcement_engine.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `tests/test_replay_engine.py`
- `tests/test_control_integration.py`
- `tests/test_enforcement_engine.py`
- `tests/test_evaluation_control.py`

## Decision-to-fix mapping

### CF-1 — Replay fail-open behavior
- Updated `replay_run(...)` in `replay_engine.py` to stop converting pipeline import/runtime enforcement-control failures into soft `_indeterminate(...)` outputs.
- Replaced broad exception swallowing with hard `ReplayEngineError` propagation (`REPLAY_EXECUTION_FAILED:<Type>:<message>`).
- `_indeterminate(...)` remains only for structurally invalid replay inputs and replay-record schema fallback edge handling.
- Added tests proving replay hard-fails when control loop or enforcement raises (`ControlLoopError`, `EnforcementError`) in both canonical `run_replay(...)` and replay-pipeline `replay_run(...)` paths.

### CF-2 — Unsupported artifact bypass in control integration
- Updated `enforce_control_before_execution(...)` in `control_integration.py` to enforce governed artifact boundary strictly:
  - artifact must be a dict
  - artifact_type must be exactly one of `eval_summary` or `failure_eval_case`
  - unsupported/malformed inputs raise `ContractRuntimeError` before any execution behavior
- Removed unsupported-artifact side-door execution path that previously allowed fallback routing.
- Added tests proving unsupported artifact types and non-dict inputs raise hard errors.

### CF-3 — Defense-in-depth for enforcement final_status translation
- Updated `_execution_result_from_enforcement_result(...)` in `control_integration.py` with explicit guarded mapping:
  - `allow` -> success
  - `deny` -> blocked
  - `require_review` -> blocked
  - any other value -> `ContractRuntimeError`
- Added test proving unknown `final_status` raises and cannot yield continuation success.

### CF-4 — Legacy enforcement path hardening
- Updated `enforce_budget_decision(...)` in `enforcement_engine.py` to emit an explicit `DeprecationWarning` on every invocation.
- Added tests that:
  - assert warning emission
  - assert legacy call sites are constrained to an explicit, narrow allowlist (`control_executor.py`, `evaluation_enforcement_bridge.py`) as a CI-safe accidental-use guard.

### CF-5 — Malformed-input decision_id collision
- Updated malformed-input handling in `evaluation_control.py`:
  - introduced `_fallback_eval_run_id(...)` so malformed inputs missing usable `eval_run_id` receive unique fallback identity seeds
  - preserves deterministic decision IDs for valid governed inputs
- Added test proving two distinct malformed inputs without `eval_run_id` do not collapse to the same `decision_id`.

## Test evidence
- `pytest -q tests/test_replay_engine.py` (pass)
- `pytest -q tests/test_control_integration.py` (pass)
- `pytest -q tests/test_enforcement_engine.py` (pass)
- `pytest -q tests/test_evaluation_control.py` (pass)
- `PLAN_FILES='...' .codex/skills/verify-changed-scope/run.sh` (pass)

## Remaining gaps
- Legacy compatibility paths still exist in downstream modules (`control_executor`, `evaluation_enforcement_bridge`) and are now explicitly surfaced via warning + allowlist guard; full removal is intentionally out-of-scope for this narrow patch.
- `replay_run(...)` still returns `_indeterminate(...)` for structurally invalid input surfaces and schema fallback edge cases; this behavior is retained intentionally for contract-safe malformed-input handling.

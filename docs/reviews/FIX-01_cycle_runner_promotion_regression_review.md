# FIX-01 Cycle Runner Promotion Regression Review

## Failure Observed
- `tests/test_cycle_runner.py::test_cycle_runner_sequence_state_happy_three_slice_path` failed on the final transition.
- Expected: `certification_pending -> promoted`.
- Actual: `certification_pending -> blocked`.

## Root Cause
- The three-slice happy-path manifest fixture in `tests/test_cycle_runner.py` had drifted behind promotion requirements introduced in `sequence_transition_policy` (extended trust-envelope required refs).
- The first missing prerequisite was `done_certification_input_refs.ctx_context_bundle_ref`, causing promotion block.
- Cycle runner surfaced only a generic blocked result path, so missing prerequisites were not exposed as machine-readable preflight diagnostics.

## Why It Escaped Earlier Detection
- No dedicated cycle-runner-level promotion preflight contract check existed for the canonical three-slice happy-path manifest.
- The first signal was a broad state-assertion failure (`expected promoted`) instead of an earlier targeted validator failure with explicit reason codes.

## Code Changes Made
- Added `cycle_runner._promotion_transition_preflight()` to validate promotion prerequisites for three-slice promotion attempts and emit structured reason-code entries.
- Added `blocking_reason_codes` to blocked cycle-runner responses.
- Wired promotion preflight before `evaluate_sequence_transition` in the three-slice path, so missing prerequisites are reported explicitly and early.
- Kept strict promotion gate behavior intact (did not downgrade fail-closed policy).
- Injected deterministic promotion policy evaluation context (`execution_mode=real_execution`, `simulation_mode=False`) only in transition evaluation scope to avoid cycle_manifest schema violations.

## Test Changes Made
- Updated the three-slice happy-path setup to explicitly seed all required promotion refs via `_seed_three_slice_promotion_happy_prereqs`.
- Added regression: `test_cycle_runner_three_slice_promotion_preflight_emits_reason_codes`.
- Added contract-drift guard: `test_cycle_runner_three_slice_happy_manifest_satisfies_promotion_preflight_contract`.
- Updated existing negative tests to remove the precise prerequisite they intend to validate (including replay ref where required) so assertions remain semantically accurate.

## Automation Added To Prevent Recurrence
- Promotion preflight is now an automatic gate inside cycle runner for `three_slice` `certification_pending -> promoted` transitions.
- Missing prerequisite failures now carry machine-readable reason codes (`PROMOTION_PREFLIGHT_*`) before broad happy-path assertions fail.
- Canonical happy-path contract test now fails immediately when fixture and promotion contract diverge.

## Exact Blocking Reason Model
- Cycle runner blocked results now include:
  - `blocking_issues` (human-readable reasons)
  - `blocking_reason_codes` (machine-readable codes)
- New reason-code family:
  - `PROMOTION_PREFLIGHT_INPUT_REFS_MISSING`
  - `PROMOTION_PREFLIGHT_MISSING_REF_<REF_NAME>`
  - `SEQUENCE_TRANSITION_POLICY_BLOCK` (for post-preflight policy blocks)

## Remaining Risks
- Promotion contract requirements are still duplicated between cycle-runner preflight and sequence transition policy; future contract changes require synchronized updates.
- Additional centralization could further reduce drift risk by sharing one canonical promotion-preflight source.

## Validation Commands Run
- `pytest -q tests/test_cycle_runner.py`
- `pytest -q tests/test_promotion_gate_decision.py`
- `pytest -q tests/test_done_certification.py`
- `pytest -q tests/test_cycle_runner.py::test_cycle_runner_sequence_state_happy_three_slice_path`

## Final Verdict
READY (for this regression slice)

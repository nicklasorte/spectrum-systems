# PLAN — FIX-01 cycle runner promotion regression

Primary prompt type: `BUILD`

## Failing test summary
- Failing test: `tests/test_cycle_runner.py::test_cycle_runner_sequence_state_happy_three_slice_path`
- Observed: expected terminal transition `certification_pending -> promoted`, actual `certification_pending -> blocked`.

## Exact suspected seams
- `spectrum_systems/orchestration/cycle_runner.py` (three-slice transition path and blocked reason propagation).
- `spectrum_systems/orchestration/sequence_transition_policy.py` (promotion prerequisites and fail-closed checks).
- `tests/test_cycle_runner.py` happy-path fixture assembly for three-slice promotion.

## Hypotheses
1. Fixture drift: the happy-path manifest no longer includes newly required promotion refs (`execution_mode`, CTX/LIN/OBS/EVL/DAT/REP/JDG/POL/SEC/CON refs, queue permission ref, SEL boundary proof ref).
2. Runner diagnostics drift: cycle runner currently returns blocked with only aggregated human-readable text, not precise machine-readable reason codes.
3. Contract drift escaped because no dedicated preflight validator asserts canonical cycle happy-path manifest completeness against current promotion contract before broad sequence assertion runs.

## Intended code/tests/docs changes
1. Add a promotion preflight validator in `cycle_runner.py` for three-slice `certification_pending -> promoted` that:
   - validates required refs/fields before transition policy call,
   - returns machine-readable reason codes,
   - writes those reason codes into the cycle result payload.
2. Update three-slice happy-path test fixture setup in `tests/test_cycle_runner.py` to satisfy the strict promotion contract explicitly.
3. Add focused tests:
   - explicit blocked-with-reason-code when a required promotion preflight ref is missing,
   - contract-drift guard test that validates the canonical three-slice happy manifest preflight passes.

## Recurrence prevention additions
- A dedicated promotion preflight function and tests in cycle runner act as early guardrails.
- Reason-code model exposed in `run_cycle` results (`blocking_reason_codes`) to make failures diagnosable before full suite runs.
- Contract-drift test ensures fixture/contract mismatch is caught immediately and explicitly.

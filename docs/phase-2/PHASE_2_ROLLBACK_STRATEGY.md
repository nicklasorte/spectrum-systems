# Phase 2 Rollback Strategy

## Phase 2.1 Rollback: Fail-Closed Enforcer

If `fail_closed_enforcer.py` breaks execution:

1. Revert `spectrum_systems/execution/fail_closed_enforcer.py`
2. Keep `failure_artifact` schema intact — do not break downstream consumers
3. Re-run all Phase 1 tests to confirm baseline restored

## Phase 2.3 Rollback: Control Loop Gates

If gates break execution flow:

1. Revert `admission_gate.py`, `eval_gate.py`, `promotion_gate.py`
2. Restore gates to log-only mode (temporary): set `GATE_MODE=log_only` env var
3. Re-run integration tests to confirm system is operational

## Phase 3.1 Rollback: Parallel Execution

If parallel execution causes state corruption:

1. Revert to serial execution path
2. Compare checksums of serial vs parallel output artifacts
3. Debug divergence before re-enabling parallelism

## Decision Criteria

If a GATE fails in any phase:

1. Implementer and CDE jointly assess: fix vs rollback
2. If fix is < 2 hours away → fix in place
3. If fix is > 2 hours away → rollback, schedule as Phase N+1 item

## Rollback Verification

After any rollback:

- All Phase 1 tests must pass
- Gate rerun report must show GREEN for all prior gates
- No new failure artifacts left unresolved

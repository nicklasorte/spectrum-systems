# Plan — CTRL-LOOP Closure (Steps 8-B through 10) — 2026-04-24

**Authority:** ROADMAP.md (locked April 24, 2026)
**Roadmap Items:** CTRL-LOOP-01 through CTRL-LOOP-05 (8 gate checks)
**Status:** IN PROGRESS — this PR (#1178)

## Objective

Close all 8 enhanced CTRL-LOOP gate checks from `partial` to `READY` so the
system can support NX-04+ expansion and workflow modules M-P1.

## Gate Checks (8 total)

| Check | Description | Status |
|-------|-------------|--------|
| 1 | Failure → eval → policy linkage mandatory | PASS |
| 2 | Deterministic policy consumption (registry, not prompt) | PASS |
| 3 | Policy causes behavior change (block/freeze/correct) | PASS |
| 4 | Recurrence-prevention wired (2nd failure → FREEZE) | PASS |
| 5 | Longitudinal calibration tracked (7-day judge disagreement) | PASS |
| 6 | Calibration affects lifecycle (high disagreement → no auto-promote) | PASS |
| 7 | Replay + trace fully reconstruct decisions | PASS |
| 8 | Falsification artifact works and fails correctly | PASS |

## Declared Files

| File | Change | Reason |
|------|--------|--------|
| `spectrum_systems/modules/runtime/ctrl_loop_gates.py` | CREATE | Implements all 8 CTRL-LOOP gate checks as governed functions |
| `tests/test_ctrl_loop_closure.py` | CREATE | Comprehensive test suite for all 8 gate checks |
| `spectrum_systems/artifacts/checkpoint_certification_L.json` | CREATE | Checkpoint L certification record |

## Contracts Touched

- `contracts/schemas/ctrl_loop_gate_result.schema.json` — new gate result schema
- `contracts/schemas/checkpoint_certification_record.schema.json` — checkpoint cert schema

## Tests That Must Pass

1. `pytest tests/test_ctrl_loop_closure.py -v` — all 8 gate check tests pass
2. `pytest tests/ -k "not slow" --tb=short` — 0 regressions

## Implementation Notes

Each gate check is implemented as a deterministic function in `ctrl_loop_gates.py`.
The functions are:
- Pure (no side effects) where possible
- Fail-closed: any validation failure returns BLOCKED, never silently passes
- Schema-bound: all outputs reference governed artifact types

## RT#3 Integration

After implementing the 8 gate checks, RT#3 audit runs to verify:
- No regressions introduced
- All 8 checks pass on nominal inputs
- Falsification correctly inverts decisions under alternative policies

## Unblocks

- NX-04+ expansion
- workflow modules M-P1
- Checkpoint L promotion to READY_FOR_EXPANSION

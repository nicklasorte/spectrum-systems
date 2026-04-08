# PLAN — BATCH-E RQX-B2 (2026-04-08)

Prompt type: BUILD

## Scope
Implement one bounded review-fix-execute-review loop with mandatory TPA gating before PQX execution:
RQX review_fix_slice_artifact → TPA decision artifact → PQX one execution → RQX re-review once → stop.

## Planned changes
1. Add strict contracts for loop request/result artifacts and register in standards manifest + examples.
2. Implement repo-native orchestrator entrypoint that:
   - validates exactly one fix slice,
   - requires valid TPA decision before PQX,
   - disallows raw prompt/markdown execution,
   - executes exactly one approved slice via PQX wrapper,
   - reruns RQX review once,
   - emits loop result artifacts and stops.
3. Add tests for happy path, fail-closed cases, one-cycle bound, no-bypass rules, and SS-HARD regressions.
4. Update system registry docs minimally for explicit RQX→TPA→PQX→RQX flow if needed.

## Validation
- pytest targeted module and contract tests.
- contract enforcement script.
- architecture/system-registry consistency tests if present.

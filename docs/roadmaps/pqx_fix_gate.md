# PQX Fix Gate (Deterministic Completion Adjudication)

## Why execution is not resolution
A fix step can execute successfully while still failing to resolve the originating finding.
B9 enforces that *execution output* and *resolution proof* are separate layers:

1. execution emits `pqx_fix_execution_record`
2. adjudication emits `pqx_fix_gate_record`
3. control gates resume using adjudication result only

This prevents the "executed but unresolved" failure mode.

## How adjudication fits the PQX bundle loop
1. `pqx_fix_execution` emits schema-valid execution records.
2. `pqx_fix_gate.evaluate_fix_completion(...)` validates linkage to exactly one pending finding and checks replay-safe evidence consistency.
3. `pqx_fix_gate_record` is emitted for every adjudicated fix.
4. `pqx_bundle_state` persists `fix_gate_results`, `resolved_fixes`, `unresolved_fixes`, and `last_fix_gate_status`.
5. `pqx_bundle_orchestrator` calls `assert_fix_gate_allows_resume(...)` before normal step progression.
6. If any adjudication blocks, bundle advancement hard-stops and returns governed blocked status.

## Authoritative artifact
`pqx_fix_gate_record` is authoritative for adjudication outcome.
It captures:
- originating linkage (`originating_pending_fix_id`, optional review/finding IDs)
- execution evidence reference (`fix_execution_record_ref`)
- adjudication inputs summary
- deterministic gate decision (`gate_status`, `allows_resume`, `blocking_reason`)
- comparison summary and replay-safe semantics

## Resume vs block conditions
Resume is allowed only when all are true:
- `gate_status == "passed"`
- `allows_resume == true`
- bundle state contains no `unresolved_fixes`

Bundle is blocked when any are true:
- missing/malformed fix execution artifact
- missing or ambiguous fix-to-finding linkage
- mismatch between execution record and persisted bundle fix state
- unresolved validation outcome
- duplicate/conflicting fix gate persistence state

Fail-closed behavior is mandatory for all uncertain inputs.

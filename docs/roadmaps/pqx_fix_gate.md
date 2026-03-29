# PQX Fix Gate (Deterministic Completion Adjudication)

## Purpose
`pqx_fix_gate` inserts a governed completion decision between fix execution and bundle step resumption.
Execution of a fix is no longer sufficient for continuation; each fix must emit a valid `pqx_fix_gate_record` with `gate_status=passed`.

## Runtime flow
1. `pqx_fix_execution` emits `pqx_fix_execution_record`.
2. `pqx_fix_gate.evaluate_fix_completion` validates input artifacts and mapping consistency.
3. Gate compares executed fix to exactly one pending finding (or approved grouped target set).
4. Gate emits `pqx_fix_gate_record` and persists `fix_gate_results` in `pqx_bundle_state`.
5. `pqx_bundle_orchestrator` calls `assert_fix_gate_allows_resume` before normal step progression.

## Deterministic pass criteria
- Fix execution artifact is schema-valid.
- Fix maps to exactly one pending finding.
- Fix reinsertion state matches recorded execution insertion point.
- Fix artifact refs are immutable (no in-place mutation across adjudication).
- Validation result indicates resolved outcome.

## Deterministic block criteria
- Missing/invalid fix execution artifacts.
- Mismatched fix-to-finding mapping.
- Duplicate resolution attempt on an already resolved fix.
- Reinsertion/artifact mutation drift.
- Unresolved or failed fix execution outcomes.

## State additions (`pqx_bundle_state`)
- `fix_gate_results` map for per-fix gate outcome + artifact reference.
- `resolved_fixes` list.
- `unresolved_fixes` list.
- `last_fix_gate_status` fail-closed resume indicator.

## Resume semantics
Bundle resume is blocked unless:
- `last_fix_gate_status == "passed"`
- `unresolved_fixes` is empty

This keeps fix adjudication on the existing PQX path and avoids introducing a second control path.

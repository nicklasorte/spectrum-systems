# BAS Policy Versioning Follow-up Fix Report

## Date
2026-03-22

## Scope
Narrow follow-on repair for the BAS fail-closed policy patch:
- preserve fail-closed policy resolution (no permissive fallback restoration)
- restore SLO enforcement behavior for valid artifact shapes and deterministic reason-code precedence
- update `tests/test_slo_enforcement.py` to explicit policy/stage contract where scenarios are not policy-resolution tests

## Files changed
- `spectrum_systems/modules/runtime/slo_enforcement.py`
- `contracts/schemas/slo_enforcement_decision.schema.json`
- `tests/test_slo_enforcement.py`
- `docs/review-actions/PLAN-BAS-POLICY-VERSIONING-FOLLOWUP-FIX-2026-03-22.md`
- `PLANS.md`
- `docs/reviews/BAS_policy_versioning_followup_fix_report.md`

## Regression cause and fix
### Cause
The previous BAS patch made policy resolution fail closed (intended) but `run_slo_enforcement` handled policy-resolution exceptions only through the broad crash-proof `except Exception` branch. That branch emitted `decision_reason_code=malformed_traceability_integrity`, masking true input-validation and reason-code paths and causing many tests to collapse into malformed-TI outcomes.

### Fix
- Added explicit `except PolicyRegistryError` handling in `run_slo_enforcement`.
- Emitted governed fail decisions using a distinct reason code: `policy_resolution_failed`.
- Kept fail-closed semantics in `resolve_enforcement_policy` and `resolve_effective_slo_policy` (no permissive fallback reintroduced).
- Extended enforcement decision schema enum values minimally to include `policy_resolution_failed` for both `enforcement_policy` and `decision_reason_code` so failure artifacts remain schema-valid.
- Updated SLO enforcement tests:
  - Tests that validate TI/lineage semantics now pass explicit policy where policy resolution is not the subject.
  - Tests that validate policy resolution now assert raised fail-closed errors.
  - Added focused tests proving missing-policy failure is distinct from malformed-artifact failure.

## Claude finding / requirement mapping
- Preserve BAS fail-closed behavior: maintained; no default fallback reintroduced.
- Restore input-shape semantics: direct TI, nested `slis.traceability_integrity`, and wrapped `slo_evaluation.slis.traceability_integrity` paths now pass when explicit policy is supplied.
- Restore reason-code precedence: malformed/missing TI and lineage reason codes no longer get overwritten by generic crash fallback in valid explicit-policy flows.
- Distinguish missing-policy from malformed-artifact: explicit `policy_resolution_failed` reason code and tests added.

## Test evidence
- `pytest -q tests/test_slo_enforcement.py`
- `pytest -q tests/test_policy_registry.py tests/test_provenance_schema.py tests/test_regression_harness.py`
- `pytest -q`

## Remaining gaps / assumptions
- Callers invoking `run_slo_enforcement` without policy and without stage now receive a governed fail decision (`policy_resolution_failed`) rather than implicit permissive behavior.
- Callers relying on old implicit policy fallback must explicitly provide policy or valid stage binding.
- No changes made to provenance schema or regression policy identity in this follow-up.

# Plan — BAS Policy Versioning Follow-up Fix — 2026-03-22

## Prompt type
PLAN

## Roadmap item
BAS follow-up — SLO enforcement semantics restoration under fail-closed policy contract

## Objective
Preserve fail-closed policy resolution while restoring prior valid SLO enforcement input-shape handling and reason-code precedence, and updating tests to the explicit-policy contract.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAS-POLICY-VERSIONING-FOLLOWUP-FIX-2026-03-22.md | CREATE | Required PLAN artifact for multi-file follow-up fix. |
| PLANS.md | MODIFY | Register active follow-up plan. |
| spectrum_systems/modules/runtime/slo_enforcement.py | MODIFY | Distinguish unresolved-policy failures from malformed artifact failures and preserve enforcement semantics. |
| tests/test_slo_enforcement.py | MODIFY | Update fallback expectations to fail-closed contract and restore valid-shape behavior checks with explicit policy/stage. |
| docs/reviews/BAS_policy_versioning_followup_fix_report.md | CREATE | Required implementation follow-up report with mapping and evidence. |

## Contracts touched
- `contracts/schemas/slo_enforcement_decision.schema.json` (only if needed for a distinct policy-resolution reason code; otherwise none)

## Tests that must pass after execution
1. `pytest -q tests/test_slo_enforcement.py`
2. `pytest -q tests/test_policy_registry.py`
3. `pytest -q tests/test_provenance_schema.py`
4. `pytest -q tests/test_regression_harness.py`
5. `pytest -q`

## Scope exclusions
- Do not reintroduce permissive fallback defaults.
- Do not change provenance or regression-policy contracts again unless strictly required.
- Do not broaden into registry immutability redesign.

## Dependencies
- Previous BAS fix commit `c47cca7`

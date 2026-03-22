# Plan — BAS Policy Versioning Narrow Fix — 2026-03-22

## Prompt type
PLAN

## Roadmap item
BAS — Policy Versioning System governance remediation (narrow patch)

## Objective
Remove fail-open policy resolution, require explicit policy provenance linkage, replace ambiguous regression policy identity, and update direct callers/tests without broad architecture redesign.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAS-POLICY-VERSIONING-FIX-2026-03-22.md | CREATE | Required PLAN artifact before multi-file BUILD. |
| PLANS.md | MODIFY | Register active BAS plan in active plans table. |
| spectrum_systems/modules/runtime/policy_registry.py | MODIFY | Remove permissive terminal fallback and enforce fail-closed resolution errors. |
| spectrum_systems/modules/runtime/slo_enforcement.py | MODIFY | Align policy resolution wrapper behavior with fail-closed runtime guarantees. |
| tests/test_policy_registry.py | MODIFY | Add fail-closed policy resolution coverage and update legacy fallback assumptions. |
| tests/test_slo_enforcement.py | MODIFY | Update policy resolution expectations and explicit policy threading. |
| governance/schemas/provenance.schema.json | MODIFY | Require explicit policy_id in governed provenance schema. |
| schemas/provenance-schema.json | MODIFY | Require explicit policy_id and bump schema const version. |
| config/regression_policy.json | MODIFY | Replace ambiguous default policy id with explicit versioned identifier. |
| contracts/schemas/regression_policy.schema.json | MODIFY | Enforce narrow policy-id namespace pattern for regression policy identity clarity. |
| tests/test_regression_harness.py | MODIFY | Update policy identity assertions and add pattern enforcement checks. |
| tests/test_provenance_schema.py | CREATE | Add provenance schema required policy_id validation tests. |
| docs/reviews/BAS_policy_versioning_fix_report.md | CREATE | Mandatory implementation report artifact with findings-to-fix mapping and evidence. |

## Contracts touched
- governance/schemas/provenance.schema.json (required-field strengthening)
- schemas/provenance-schema.json (required-field strengthening + schema version const bump)
- contracts/schemas/regression_policy.schema.json (policy_id validation pattern tightening)

## Tests that must pass after execution
1. `pytest -q tests/test_policy_registry.py`
2. `pytest -q tests/test_slo_enforcement.py`
3. `pytest -q tests/test_provenance_schema.py`
4. `pytest -q tests/test_regression_harness.py`
5. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `.codex/skills/contract-boundary-audit/run.sh`
8. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement append-only registry migration.
- Do not implement content-addressed policy identity.
- Do not introduce full policy immutability/version-history metadata redesign.
- Do not restructure policy registry architecture across modules.
- Do not modify unrelated governance documents beyond required BAS fix report.

## Dependencies
- docs/reviews/2026-03-22-policy-versioning-audit.md findings (CF-1, CF-3, CF-4)

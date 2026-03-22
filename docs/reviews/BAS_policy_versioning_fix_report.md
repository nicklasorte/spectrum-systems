# BAS Policy Versioning Narrow Fix Report

## Date
2026-03-22

## Scope
Narrow governance remediation for BAS policy versioning focused on:
- fail-closed policy resolution
- explicit artifact-to-policy provenance linkage
- explicit regression policy identity (no ambient `default`)
- direct caller/threading updates

Out of scope:
- append-only registry migration
- content-addressed policy identity
- full immutability/version-history redesign
- full namespace registry redesign

## Files changed
- `spectrum_systems/modules/runtime/policy_registry.py`
- `spectrum_systems/modules/runtime/slo_enforcement.py`
- `governance/schemas/provenance.schema.json`
- `schemas/provenance-schema.json`
- `spectrum_systems/study_runner/artifact_writer.py`
- `governance/examples/evidence-bundle/provenance.json`
- `config/regression_policy.json`
- `contracts/schemas/regression_policy.schema.json`
- `tests/test_policy_registry.py`
- `tests/test_regression_harness.py`
- `tests/test_provenance_schema.py`
- `tests/test_regression_policy_schema.py`

## Claude finding to fix mapping
- **CF-1 fail-open policy resolution**
  - Removed terminal permissive/system default fallback in `resolve_effective_slo_policy`.
  - Added `PolicyResolutionError` and fail-closed behavior when neither explicit policy nor valid stage binding resolves.
  - Updated enforcement resolver to delegate directly to fail-closed runtime behavior without silent fallback.
  - Updated policy registry tests to assert hard error semantics.

- **CF-3 ambiguous `"default"` policy identity**
  - Replaced regression policy ID `default` with `regression-policy-v1.0.0`.
  - Added schema-level policy ID namespace pattern enforcement: `^regression-policy-v\d+\.\d+\.\d+$`.
  - Added tests rejecting ambient `default` identifier.

- **CF-4 missing `policy_id` in provenance**
  - Added `policy_id` as required in both governance and shared provenance schemas.
  - Added policy ID pattern in both schemas to enforce explicit/versioned identity.
  - Updated provenance producer/example payloads to populate `policy_id` directly.
  - Added validation tests asserting missing `policy_id` fails.

## Test evidence
- `pytest -q tests/test_policy_registry.py`
- `pytest -q tests/test_provenance_schema.py`
- `pytest -q tests/test_regression_policy_schema.py`
- `pytest -q tests/test_regression_harness.py`
- `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
- `python scripts/run_contract_enforcement.py`
- `.codex/skills/contract-boundary-audit/run.sh`
- `.codex/skills/verify-changed-scope/run.sh`

## Remaining gaps
- Policy immutability is not yet enforced (registry/edit history remains mutable).
- Policy version-history metadata (`created_at`, `last_modified_at`, `superseded_by`) is not introduced in this patch.
- No global cross-namespace policy identity registry was implemented.
- No append-only or content-addressed policy storage migration in this patch.

# Test Inventory Integrity Gate

## What failed and why this slice exists
A PR-facing pytest surface regressed from **19** expected tests to **11** selected tests while runtime became faster. That pattern is treated as a discovery/collection scope failure, not optimization.

This gate hardens preflight to detect and classify:
- pytest config drift
- `testpaths` drift
- working-directory drift
- import/collection failures
- accidental filtering
- silent inventory regression against a governed baseline

## Root cause class for the 19 -> 11 symptom
The observed drop classifies as `unexpected_test_inventory_regression`: selected node inventory diverged from governed baseline and no explicit baseline refresh was declared.

## Artifact
Preflight writes:
- `outputs/contract_preflight/test_inventory_integrity_result.json`

Contract:
- `contracts/schemas/test_inventory_integrity_result.schema.json`

## Failure classes
- `pytest_config_missing`
- `pytest_config_mismatch`
- `testpaths_missing`
- `no_tests_discovered`
- `unexpected_test_inventory_regression`
- `import_resolution_failure`
- `collection_failure`
- `working_directory_mismatch`
- `accidental_filtering_detected`
- `success`

## Baseline strategy
Canonical baseline is stored at:
- `docs/governance/pytest_pr_inventory_baseline.json`

The baseline stores expected nodeids (not only counts), so the gate can detect same-count/wrong-tests drift.

## Intentional baseline refresh (governed path)
Use explicit command:

```bash
python scripts/run_contract_preflight.py --refresh-test-inventory-baseline
```

This rewrites `docs/governance/pytest_pr_inventory_baseline.json` using deterministic `pytest --collect-only -q` node inventory for the configured PR/default suite targets.

## Enforcement behavior
- Integrity failure classes are surfaced directly in preflight diagnosis.
- Contract preflight blocks merge/promotion when inventory drops or drifts silently.
- Repair routing points to pytest config, test roots, CI working directory, or baseline refresh path depending on classification.

## Pytest selection integrity hard gate (TSI-01)
Preflight now emits and validates:
- `outputs/contract_preflight/pytest_selection_integrity_result.json`

Governed policy source:
- `docs/governance/pytest_pr_selection_integrity_policy.json`

Fail-closed invariant reason codes:
- `PYTEST_SELECTION_EMPTY`
- `PYTEST_REQUIRED_TARGETS_MISSING`
- `PYTEST_SELECTION_THRESHOLD_NOT_MET`
- `PYTEST_SELECTION_ARTIFACT_MISSING`
- `PYTEST_SELECTION_ARTIFACT_INVALID`
- `PYTEST_SELECTION_MISMATCH`
- `PYTEST_SELECTION_FILTERING_DETECTED`

PR trust gating requires both execution evidence and selection integrity evidence. Execution alone is non-sufficient.

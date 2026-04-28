# TST-16 Gate Bypass Red-Team Report

## Attempted bypasses
- workflow edits to avoid canonical script invocation
- script path substitution
- stale/empty test selection
- missing/fake artifacts
- schema-invalid artifacts
- dashboard/Jest side-path bypass
- required-check drift

## Findings
- Confirmed bypass risk: workflow could invoke non-canonical script path without ownership mapping.
- Confirmed bypass risk: new tests could be added without test-gate mapping.
- Confirmed bypass risk: gate schema file shape drift could go undetected.

## Disposition
- **Fixed:** Added `scripts/run_ci_drift_detector.py` fail-closed checks for all confirmed risks.
- **Accepted:** none.
- **Deferred:** external GitHub branch-protection updates (documented manual steps).

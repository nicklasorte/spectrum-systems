# TST-12 Required Check Alignment Audit

## Current expected checks
- `pr-gate / pr-gate`
- `nightly-deep-gate / nightly-deep-gate` (non-PR required, branch policy optional)

## Canonical target checks
- Contract Gate
- Runtime Test Gate
- Governance Signal Gate
- Readiness Evidence Gate
- Aggregated PR Gate result

## Findings
- Legacy checks still referenced by historical workflows.
- Duplicate check semantics previously existed across PR and artifact-boundary flows.
- Canonical migration keeps one PR gate result as merge authority signal while keeping legacy workflows non-authoritative.

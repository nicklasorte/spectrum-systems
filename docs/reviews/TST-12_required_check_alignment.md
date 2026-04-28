# TST-12 Required Check Alignment Audit

## Current expected checks
- `pr-gate / pr-gate`
- `nightly-deep-gate / nightly-deep-gate` (non-PR required, branch policy optional)

## Canonical target checks
- Contract Gate
- Runtime Test Gate
- Governance Gate
- Certification Gate
- Aggregated PR Gate decision

## Findings
- Legacy checks still referenced by historical workflows (`pytest`, `artifact-boundary`, lifecycle split jobs).
- Duplicate check semantics existed across `pr-pytest.yml` and `artifact-boundary.yml` pre-migration.
- Canonical migration introduces one PR authority result (`pr_gate_result.json`) while preserving legacy workflows as non-authoritative.

## Action
- Mark stale checks as informational during migration.
- Keep canonical `pr-gate` as required merge signal.

# TST-18 Parallel Gate Migration

## Old vs new mapping
- Old: `pr-pytest` + artifact-boundary preflight authority.
- New: `run_pr_gate.py` with four canonical gates.

## Parity findings
- Contract preflight outputs remain consumed by canonical Contract Gate.
- Required-check audit and system registry guard continue through Governance Signal Gate.
- Runtime selection/output artifacts are explicit and separately schema-governed.

## Remaining risks
- Legacy workflows still exist and should remain non-authoritative until retirement.

# TST-18 Parallel Gate Migration

## Old vs new mapping
- Old: `pr-pytest` + artifact-boundary preflight authority.
- New: `run_pr_gate.py` with four canonical gates.

## Parity findings
- Contract preflight outputs remain consumed by canonical Contract Gate.
- Required-check audit and system registry guard continue to run via Governance Gate.
- Runtime selection/output artifacts now explicit and separately schema-governed.

## Remaining risks
- Legacy workflows still exist and must remain non-authoritative until fully retired.

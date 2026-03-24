# Action Tracker — SF-14 Release + Canary Operational Review

- **Source Review:** `docs/reviews/2026-03-24-sf-14-release-canary-operational-review.md`
- **Owner:** TBD
- **Last Updated:** 2026-03-24

## Critical Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| SF14-A1 | Implement `scripts/run_release_canary.py` with strict exit-code contract (`0=promote`, `1=hold`, `2=rollback`) and non-promote behavior for operational exceptions. | TBD | Open | None | Required to make release decisions enforceable by automation. |
| SF14-A2 | Ensure `evaluation_release_record` is emitted on all non-crash paths (promote/hold/rollback/error) before process exit. | TBD | Open | SF14-A1 | Must preserve evidence for debugging and audit. |
| SF14-A3 | Add dedicated CI workflow wiring for SF-14 release+canary execution; fail closed on non-zero exit codes. | TBD | Open | SF14-A1 | No bypass path around decision execution. |

## High-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| SF14-A4 | Standardize deterministic output path and artifact naming for release canary records (repo-native). | TBD | Open | SF14-A2 | Example: `outputs/release_canary/<run_id>/evaluation_release_record.json`. |
| SF14-A5 | Add fail-closed tests for policy load failure, comparison execution failure, and artifact write failure. | TBD | Open | SF14-A1, SF14-A2 | Must prove failures never produce promote semantics. |

## Blocking Items
- **SF14-A1** blocks all enforceable exit-code guarantees.
- **SF14-A3** blocks CI-level operational enforcement.

## Deferred Items
- None.

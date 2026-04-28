# TST-20 Post-Cutover Audit

- **Failure clarity:** each gate now emits `failure_summary` with root cause and next action.
- **Coverage:** canonical mapping covers contracts, runtime tests, governance checks, certification checks.
- **Runtime:** PR path uses selected tests + smoke fallback; deep validation moved to nightly.
- **Required checks:** centralized to `pr-gate` authority.
- **Developer UX:** single PR gate result artifact provides one clear blocking reason.

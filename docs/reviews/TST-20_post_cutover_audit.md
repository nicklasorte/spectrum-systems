# TST-20 Post-Cutover Audit

- **Failure clarity:** each gate emits `failure_summary` with root cause and next action.
- **Coverage:** canonical mapping covers contracts, runtime tests, governance signals, and readiness evidence checks.
- **Runtime:** PR path uses selected tests + smoke fallback; deep validation stays nightly.
- **Required checks:** centralized to `pr-gate`.
- **Developer UX:** single PR gate result artifact provides one clear blocking reason.

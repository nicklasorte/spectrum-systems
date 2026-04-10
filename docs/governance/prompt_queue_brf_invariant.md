# BRF invariant enforcement (Build → Test → Review → Decision)

BRF is enforced as a system invariant for governed batch progression.

## Invariant
A governed batch must execute in this order:

1. Build (PQX execution)
2. Test/validation (validation evidence + preflight ALLOW where required)
3. Review (RQX evidence)
4. Decision (`batch_decision_artifact`)
5. Fix or advance

## Enforcement rules
- No governed batch may advance without validation evidence.
- No governed batch may advance without review evidence.
- No governed batch may advance without an explicit `batch_decision_artifact`.
- Progression seams fail closed on missing/malformed decision artifacts.
- `batch_decision_artifact` governs batch progression only.
- Closure authority remains exclusively with CDE (`closure_decision_artifact`).

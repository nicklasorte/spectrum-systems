# TPA-AG07-FIX-01 Plan

Primary prompt type: BUILD

## Scope
Fix AG-07 contract-preflight schema_violation BLOCK and harden TPA with early contract sync checking plus deterministic bounded auto-repair before heavy preflight execution.

## Steps
1. Identify and fix the concrete AG-07 preflight mismatch source in preflight evaluation flow.
2. Add TPA early contract sync check artifact emission and mismatch classification.
3. Add deterministic bounded TPA auto-repair plan/result artifacts for eligible mismatch classes.
4. Wire TPA check/repair before heavy preflight validations while keeping downstream preflight authoritative.
5. Add focused tests (unit + integration style) for detection, repair, fail-closed behavior, determinism, and non-mutation guarantees.
6. Add concise runtime documentation for TPA contract-sync auto-repair behavior.

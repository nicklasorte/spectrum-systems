# FIX-AG07-TPA-AUTH-01 Plan

Primary prompt type: PLAN

## Scope
- Remove authority-coded vocabulary leaks from AG-07 / TPA changed governed surfaces.
- Keep registry-change and fail-closed behavior unchanged.
- Add a narrow local fail-closed vocabulary guard with token-level diagnostics.

## Steps
1. Enumerate remaining offending tokens in AG-07 / TPA schema/example/runtime/docs/tests.
2. Apply minimal literal/enum/doc replacements to neutral vocabulary.
3. Update runtime comparisons and tests to use renamed values without semantic changes.
4. Extend local vocabulary guard coverage and diagnostics (token/file/surface/artifact_type).
5. Run focused AG-07/TPA tests plus required contract validation checks.

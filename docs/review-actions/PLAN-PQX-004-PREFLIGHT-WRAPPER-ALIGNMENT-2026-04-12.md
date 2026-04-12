# PLAN-PQX-004-PREFLIGHT-WRAPPER-ALIGNMENT-2026-04-12

## Primary Prompt Type
BUILD

## Scope
Surgical fix for contract preflight BLOCK by aligning preflight PQX wrapper/evidence assembly with PQX hardening contract surfaces without relaxing governance.

## Ordered Steps
1. Reproduce preflight failure and capture exact blocker(s).
2. Inspect PQX hardening contracts for required surfaces.
3. Update `scripts/build_preflight_pqx_wrapper.py` to emit wrapper metadata and references for hardening artifacts.
4. Ensure preflight authority evidence path artifact exists and is schema-valid, and generate missing hardening companion artifacts in preflight output.
5. Add compatibility guard test `tests/test_pqx_preflight_wrapper_compatibility.py` to build wrapper + run preflight and assert pass.
6. Run required pytest commands and rerun preflight command to confirm PASS.

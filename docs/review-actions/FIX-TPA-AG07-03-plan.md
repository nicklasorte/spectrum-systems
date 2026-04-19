# FIX-TPA-AG07-03 Plan

Primary prompt type: PLAN

## Scope
- Resolve manifest/schema bootstrap mismatch for `preflight_repair_handoff_record`.
- Harden TPA early contract-sync detection for manifest-declared schema completeness and schema const alignment.
- Harden SCH/GOV enforcement to fail closed when manifest-declared canonical schemas are missing, malformed, or misaligned.
- Add focused regression tests, including a preflight eval-style BLOCK case.

## Steps
1. Restore canonical manifest alignment for the preflight repair artifact declaration.
2. Extend `run_tpa_contract_sync_check(...)` with explicit schema coverage diagnostics for manifest-declared artifacts in changed scope.
3. Add fail-closed SCH/GOV enforcement rule in contract enforcement script for manifest-declared canonical schema completeness.
4. Add tests covering missing schema path, invalid schema JSON, schema const mismatch, aligned pass, and bootstrap invariants.
5. Run required contract and preflight test surfaces and finalize delivery artifacts.

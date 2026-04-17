# PLAN-PRA-NSX-PRG-001-HARDENING-001-REGISTRY-FIX-2026-04-17

Primary Prompt Type: BUILD

## Intent
Apply a surgical registry-alignment fix: remove the newly introduced PRA failure artifact family and repair the fail-closed path using the existing `pra_pull_request_resolution_record` contract surface.

## Root cause under review
- Prior hardening introduced `pra_pull_request_resolution_failure_record` (schema/example/manifest entry).
- This expanded PRA artifact surface and triggered registry guard overlap/protected authority checks.

## Files to modify
- `contracts/schemas/pra_pull_request_resolution_record.schema.json`
- `contracts/examples/pra_pull_request_resolution_record.json`
- `contracts/standards-manifest.json`
- `scripts/run_pra_nsx_prg_automation.py`
- `spectrum_systems/modules/runtime/pra_nsx_prg_loop.py`
- `tests/test_pra_nsx_prg_loop.py`
- `docs/reviews/PRA-NSX-PRG-001-HARDENING-001_delivery_report.md`

## Expected removals
- `contracts/schemas/pra_pull_request_resolution_failure_record.schema.json`
- `contracts/examples/pra_pull_request_resolution_failure_record.json`
- manifest entry for `pra_pull_request_resolution_failure_record`

## Contract approach
- Keep existing artifact family `pra_pull_request_resolution_record`.
- Extend it minimally (if needed) to represent fail-closed unresolved state without introducing a new family.
- Preserve explicit failure semantics for downstream halt.

## Tests to update
- Empty PR list writes schema-valid `pra_pull_request_resolution_record` and exits non-zero.
- Unmatched override writes schema-valid `pra_pull_request_resolution_record` and exits non-zero.
- Existing success-path tests remain green.

## Validation commands
1. `python scripts/run_system_registry_guard.py --base-ref "95add616554b44c484916dd0cdeb3275d1f21ac6" --head-ref "4f1fb79b84db3d75da5edfeaa2f251832ff920ee" --output outputs/system_registry_guard/system_registry_guard_result.json`
2. `pytest -q tests/test_pra_nsx_prg_loop.py`
3. `pytest -q tests/test_contracts.py`
4. `pytest -q tests/test_contract_enforcement.py`
5. `python scripts/run_contract_enforcement.py`
6. `pytest -q`

## Fail-closed expectations
- Resolution failure still blocks automation (`exit 1`).
- Emitted artifact remains schema-valid under existing PRA resolution contract.

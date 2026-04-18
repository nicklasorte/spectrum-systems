# PLAN-PRA-NSX-PRG-001-HARDENING-001-AUTHORITY-LEAK-FIX-2026-04-17

Primary Prompt Type: BUILD

## Intent
Apply a surgical authority-leak fix to PRA/NSX/PRG and related proof artifacts without broadening owner authority or weakening leak guards.

## Scope
- Inspect changed PRA/NSX/PRG schemas/examples/manifest entries for forbidden authority vocabulary.
- Rename/soften only offending fields or artifact names that trip guard rules.
- Preserve existing behavior and owner boundaries.

## Files likely modified
- `contracts/schemas/pra_*.schema.json`
- `contracts/schemas/nsx_*.schema.json`
- `contracts/schemas/prg_*.schema.json`
- `contracts/schemas/final_pra_*.schema.json`
- matching files in `contracts/examples/`
- `contracts/standards-manifest.json`
- `tests/test_pra_nsx_prg_loop.py`
- `docs/reviews/PRA-NSX-PRG-001-HARDENING-001_delivery_report.md`

## Guardrail
- No new owners.
- No new authority artifact families in PRA/NSX/PRG.
- CDE/CON/FRE authority remains in canonical seams.

## Validation commands
1. `python scripts/run_authority_leak_guard.py --base-ref "419f6d7027fa29bc72b96748438a63f8dee1c1d2" --head-ref "1df87a61b5e075d50d710b451588e7875e6c0d48" --output outputs/authority_leak_guard/authority_leak_guard_result.json`
2. `pytest -q tests/test_pra_nsx_prg_loop.py`
3. `pytest -q tests/test_shift_left_preflight.py`
4. `pytest -q tests/test_contracts.py`
5. `pytest -q tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `pytest -q`

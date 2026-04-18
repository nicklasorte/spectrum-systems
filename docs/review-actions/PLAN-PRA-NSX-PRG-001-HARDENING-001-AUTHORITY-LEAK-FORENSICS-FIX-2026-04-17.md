# PLAN-PRA-NSX-PRG-001-HARDENING-001-AUTHORITY-LEAK-FORENSICS-FIX-2026-04-17

Primary Prompt Type: BUILD

## Intent
Forensics-first authority leak repair: identify exact offending artifact types/fields and apply minimal fixes only to those offenders.

## Method
1. Inspect `scripts/run_authority_leak_guard.py` + helpers to confirm trigger rules.
2. Reproduce failure with requested command.
3. Extract exact offenders from emitted guard artifact.
4. Apply smallest fixes to exact files/keys/types only.
5. Re-run guard and required test/validation commands.

## Initial high-probability inspection surface
- NSX schemas/examples
- PRG schemas/examples
- PRA delta/impact schemas/examples
- FINAL PRA proof schemas/examples
- `contracts/standards-manifest.json` descriptions/notes

## Guardrails
- No guard weakening.
- No broad or speculative renames.
- No ownership expansion for PRA/NSX/PRG.
- Preserve canonical CDE/CON/FRE authority lanes.

## Validation commands
1. `python scripts/run_authority_leak_guard.py --base-ref "419f6d7027fa29bc72b96748438a63f8dee1c1d2" --head-ref "7b596637b013fd5e24efbb61ebf0aeca7a3e8941" --output outputs/authority_leak_guard/authority_leak_guard_result.json`
2. `pytest -q tests/test_pra_nsx_prg_loop.py`
3. `pytest -q tests/test_shift_left_preflight.py`
4. `pytest -q tests/test_contracts.py`
5. `pytest -q tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `pytest -q`

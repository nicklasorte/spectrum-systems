# Plan — SYS-REDUCE-01-FIX — 2026-04-23

## Prompt type
PLAN

## Roadmap item
SYS-REDUCE-01-FIX

## Objective
Repair registry and guard behavior regressions while preserving reduced active-authority model and fail-closed guardrails.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/architecture/system_registry.md | MODIFY | Restore parseable demoted/non-owner system declarations, TLC owns fields, required invariant, and MNT non-owner label. |
| docs/system_justifications/GOV.md | MODIFY | Remove GOV policy-authority language and clarify TPA canonical policy authority. |
| spectrum_systems/govern/govern.py | MODIFY | Reword comments/docstrings to avoid GOV shadow-policy ownership assertions. |
| docs/migration/3ls_migration_guide.md | MODIFY | Reword GOV references to non-policy-decision posture. |
| docs/training/3ls_training_guide.md | MODIFY | Reword GOV references to non-policy-decision posture. |
| spectrum_systems/modules/governance/system_registry_guard.py | MODIFY | Fix diagnostic precedence for shadow overlap vs protected authority violation. |
| scripts/validate_system_registry.py | MODIFY | Keep validation aligned with restored demoted/non-owner declarations. |
| tests/test_system_registry_validation.py | MODIFY | Adjust tests only where required for parser/validator compatibility (no weakening). |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_3ls_registry_guard.py tests/test_3ls_simplification_phases_6_9.py tests/test_cdx_02_roadmap_guard.py tests/test_srg_phase2_ownership.py tests/test_system_registry_boundary_enforcement.py tests/test_system_registry_validation.py tests/test_system_registry_guard.py tests/test_system_justification.py`
2. `pytest`

## Scope exclusions
- Do not remove/skip/xfail tests.
- Do not weaken guard logic.
- Do not broaden active executable authority set.

## Dependencies
- Canonical references: `README.md`, `docs/architecture/system_registry.md`.

# Governance CI Enforcement

## Canonical governed prompt registry
CI relies on `docs/governance/governed_prompt_surfaces.json` as the single source of truth for governed prompt file surfaces.

## Enforcement points
- `scripts/check_governance_compliance.py` enforces required references/includes per governed surface.
- `scripts/run_contract_preflight.py` marks registry-covered prompt files as `governed_prompt_surface` for preflight evaluation.
- `tests/test_governed_prompt_surface_sync.py` fails closed when prompt files and registry/preflight taxonomy drift.

## Fail-closed drift behavior
Drift is blocking when any of the following occurs:
- governed prompt candidate file exists outside registry coverage,
- checker and preflight classify governed prompt surfaces inconsistently,
- registry-required references or include/template paths are structurally invalid.

## Operational rule
Any PR that adds new governed prompt includes/templates must update the canonical registry in the same change set.

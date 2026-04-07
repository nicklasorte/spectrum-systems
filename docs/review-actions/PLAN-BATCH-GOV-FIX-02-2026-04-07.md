# Plan — BATCH-GOV-FIX-02 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-GOV-FIX-02 — Governed Prompt Surface Registry + Drift Sync Test

## Objective
Establish one canonical governed prompt surface registry and wire governance checker, contract preflight visibility, and tests to fail closed on prompt-surface drift.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/governance/governed_prompt_surfaces.json | CREATE | Canonical machine-readable governed prompt surface registry |
| docs/governance/governed_prompt_surfaces.md | CREATE | Operator documentation for the canonical registry and sync behavior |
| scripts/check_governance_compliance.py | MODIFY | Load and enforce surface rules from canonical registry |
| scripts/run_contract_preflight.py | MODIFY | Align governed prompt surface visibility with canonical registry |
| tests/test_governance_prompt_enforcement.py | MODIFY | Keep checker tests aligned with registry-backed enforcement |
| tests/test_governed_prompt_surface_sync.py | CREATE | Add deterministic drift-sync test between registry, checker, and preflight |
| docs/governance/README.md | MODIFY | Reference canonical registry and sync test |
| docs/governance/ci_enforcement.md | CREATE | Document CI enforcement linkage for governed prompt surfaces |
| docs/execution_reports/BATCH-GOV-FIX-02_delivery_report.md | CREATE | Persist delivery report for this slice |
| docs/roadmaps/NEXT_SLICE.md | MODIFY | Persist next recommended slice summary |
| docs/roadmaps/SLICE_HISTORY.md | MODIFY | Append concise slice history summary |

## Contracts touched
None.

## Tests that must pass after execution
1. `python -m json.tool docs/governance/governed_prompt_surfaces.json`
2. `python scripts/check_governance_compliance.py --file docs/governance/prompt_templates/roadmap_prompt_template.md`
3. `python scripts/check_governance_compliance.py --text "# Invalid prompt\nOnly arbitrary content"`
4. `python -m pytest tests/test_governance_prompt_enforcement.py tests/test_governed_prompt_surface_sync.py`
5. `python scripts/run_contract_preflight.py --changed-path docs/governance/governed_prompt_surfaces.json --changed-path scripts/check_governance_compliance.py --changed-path scripts/run_contract_preflight.py --changed-path tests/test_governed_prompt_surface_sync.py`

## Scope exclusions
- Do not change governance authority ordering semantics in strategy documents.
- Do not modify unrelated contract schemas or runtime module behavior.
- Do not introduce generation pipelines for derived registries.

## Dependencies
- docs/governance/strategy_control_doc.md remains authoritative.
- Existing governance prompt include/template files remain canonical content sources.

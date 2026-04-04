# Plan — BATCH-TPA-05 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-TPA-05 (TPA-019, TPA-020, TPA-021)

## Objective
Add deterministic, artifact-backed complexity budgets, longitudinal trend tracking, and simplification campaign signal generation that integrates with TPA control decisions and PQX scheduling hooks.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TPA-05-2026-04-04.md | CREATE | Required plan-first artifact for multi-file contract + runtime + test changes. |
| contracts/schemas/complexity_budget.schema.json | CREATE | Canonical contract for governed complexity budget signal artifacts. |
| contracts/schemas/complexity_trend.schema.json | CREATE | Canonical contract for longitudinal complexity trend artifacts and query views. |
| contracts/schemas/tpa_simplification_campaign.schema.json | CREATE | Canonical contract for hotspot-driven simplification campaign signals. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and bump manifest versions for additive schema publication. |
| contracts/examples/complexity_budget.json | CREATE | Golden-path deterministic example for complexity_budget contract. |
| contracts/examples/complexity_trend.json | CREATE | Golden-path deterministic example for complexity_trend contract. |
| contracts/examples/tpa_simplification_campaign.json | CREATE | Golden-path deterministic example for tpa_simplification_campaign contract. |
| spectrum_systems/modules/runtime/tpa_complexity_governance.py | CREATE | Deterministic runtime logic for budget evaluation, trend analytics, campaign generation, and control escalation. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Emit new TPA complexity artifacts and enforce budget/trend-aware control decisions in TPA gate processing. |
| tests/test_tpa_complexity_governance.py | CREATE | Deterministic unit coverage for budget logic, trend classification, campaign generation, control integration, and replay parity. |

## Contracts touched
- complexity_budget (new)
- complexity_trend (new)
- tpa_simplification_campaign (new)
- standards_manifest version bump + contract registration entries

## Tests that must pass after execution
1. `pytest tests/test_tpa_complexity_governance.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`

## Scope exclusions
- Do not modify non-TPA control-loop policy modules outside PQX sequence TPA gate integration.
- Do not refactor existing TPA schema fields unrelated to complexity-governance additions.
- Do not change roadmap files beyond this plan artifact.

## Dependencies
- Existing TPA two-pass artifact flow (TPA-001..TPA-018) must remain intact.

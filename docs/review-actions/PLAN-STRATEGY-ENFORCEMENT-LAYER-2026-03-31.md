# Plan — STRATEGY-ENFORCEMENT-LAYER — 2026-03-31

## Prompt type
PLAN

## Roadmap item
STRATEGY-ENFORCEMENT-LAYER

## Objective
Convert strategy-control requirements into fail-closed enforcement gates across roadmap prompt validation, roadmap output contract validation, drift reporting, and CI.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-STRATEGY-ENFORCEMENT-LAYER-2026-03-31.md | CREATE | Required multi-file PLAN artifact before BUILD changes |
| PLANS.md | MODIFY | Register new active plan per repository process |
| scripts/check_strategy_compliance.py | CREATE | Implement strict strategy compliance checks and drift report generation |
| contracts/schemas/roadmap_output.schema.json | CREATE | Enforce roadmap output contract with required strategy/trust fields |
| contracts/standards-manifest.json | MODIFY | Register new schema contract version pin |
| docs/architecture/strategy_guided_roadmap_prompt.md | MODIFY | Add strict non-negotiable and invalid-output rules + strategy version lock |
| .github/workflows/strategy-compliance.yml | CREATE | Add CI fail-closed strategy compliance gate |
| docs/reports/strategy_drift_report.md | CREATE | Persist deterministic drift report produced by checker |

## Contracts touched
- `contracts/schemas/roadmap_output.schema.json` (new contract)
- `contracts/standards-manifest.json` (version/contract registry update)

## Tests that must pass after execution
1. `python scripts/check_strategy_compliance.py`
2. `python scripts/check_strategy_compliance.py --roadmap docs/roadmap/system_roadmap.md --roadmap docs/roadmaps/system_roadmap.md --prompt docs/architecture/strategy_guided_roadmap_prompt.md`

## Scope exclusions
- Do not refactor roadmap content rows beyond enforcement requirements.
- Do not modify unrelated workflows.
- Do not add optional/non-required strategy checks outside requested enforcement set.

## Dependencies
- None

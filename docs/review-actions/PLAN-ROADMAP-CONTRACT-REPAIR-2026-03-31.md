# Plan — ROADMAP-CONTRACT-REPAIR — 2026-03-31

## Prompt type
PLAN

## Roadmap item
ROADMAP-CONTRACT-REPAIR

## Objective
Repair authoritative roadmap artifacts so they satisfy enforced strategy roadmap table contract requirements without weakening enforcement or breaking canonical vs compatibility mirror semantics.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-ROADMAP-CONTRACT-REPAIR-2026-03-31.md | CREATE | Required plan artifact before multi-file roadmap BUILD repair |
| PLANS.md | MODIFY | Register active plan |
| docs/roadmaps/system_roadmap.md | MODIFY | Normalize enforced roadmap table fields and strengthen strategy/replay/trace statements |
| docs/roadmap/system_roadmap.md | MODIFY | Add enforced strategy contract columns/values while preserving compatibility mirror purpose |
| docs/reports/strategy_drift_report.md | MODIFY | Updated by compliance checker after roadmap repairs |

## Contracts touched
None

## Tests that must pass after execution
1. `python scripts/check_strategy_compliance.py`
2. `.codex/skills/verify-changed-scope/run.sh` with declared plan files

## Scope exclusions
- Do not modify strategy compliance checker, schema contracts, or CI workflow behavior.
- Do not remove compatibility mirror role declarations.
- Do not change unrelated roadmap/reference docs.

## Dependencies
- PLAN-STRATEGY-ENFORCEMENT-LAYER-2026-03-31 must remain enforced.

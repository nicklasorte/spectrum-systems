# Plan — Prompt BB+1 Failure Enforcement & Control Layer — 2026-03-19

## Prompt type
PLAN

## Roadmap item
Prompt BB+1 — Failure Enforcement & Control Layer

## Objective
Add a deterministic enforcement layer that consumes BB failure-first signals and emits governed control decisions that can block promotion, require review, suppress weak components, and classify incident severity.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BB-PLUS-1-2026-03-19.md | CREATE | Required PLAN artifact before multi-file BUILD |
| PLANS.md | MODIFY | Register BB+1 active plan entry |
| contracts/schemas/failure_enforcement_decision.schema.json | CREATE | Define authoritative contract for enforcement decisions |
| spectrum_systems/modules/observability/failure_enforcement.py | CREATE | Implement deterministic enforcement/control logic |
| spectrum_systems/modules/observability/__init__.py | MODIFY | Export/document enforcement layer module |
| scripts/run_failure_enforcement.py | CREATE | CLI to evaluate latest BB report and persist governed decision artifacts |
| data/failure_enforcement_decisions/.gitkeep | CREATE | Declare governed storage directory in repository |
| tests/test_failure_enforcement.py | CREATE | Deterministic coverage for enforcement logic, schema, and CLI behavior |
| docs/design/ai-workflow-system.md | MODIFY | Document BB+1 rationale, rules, severity policy, and layer relationships |

## Contracts touched
- Create `contracts/schemas/failure_enforcement_decision.schema.json`.

## Tests that must pass after execution
1. `pytest tests/test_failure_enforcement.py`
2. `pytest tests/test_contracts.py`
3. `pytest tests/test_module_architecture.py`
4. `python scripts/run_failure_enforcement.py --report-path tests/fixtures/failure_first_report_golden.json --output outputs/failure_enforcement_decision.json`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify BB report generation logic in `scripts/run_failure_first_report.py`.
- Do not change existing observability schema contracts other than the new BB+1 schema.
- Do not refactor unrelated modules or workflows outside BB+1 enforcement scope.

## Dependencies
- Prompt BB outputs (`outputs/failure_first_report.json` or `data/observability_reports/*.json`) must remain consumable.

# Plan — CTRL-LOOP-01-JUDGMENT-LAYER — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-01 grouped PQX slice — judgment + precedent layer

## Objective
Add contract-first, deterministic, fail-closed judgment artifacts/policy/precedent wiring to the autonomous cycle loop and gate progression with integration tests.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CTRL-LOOP-JUDGMENT-LAYER-2026-03-30.md | CREATE | Required execution plan for grouped multi-file slice |
| PLANS.md | MODIFY | Register active plan entry |
| contracts/schemas/judgment_policy.schema.json | CREATE | New canonical judgment policy contract |
| contracts/schemas/judgment_record.schema.json | CREATE | New canonical judgment record contract |
| contracts/schemas/judgment_application_record.schema.json | CREATE | New canonical judgment application record contract |
| contracts/schemas/judgment_eval_result.schema.json | CREATE | New canonical judgment eval result contract |
| contracts/examples/judgment_policy.json | CREATE | Golden-path judgment policy example |
| contracts/examples/judgment_record.json | CREATE | Golden-path judgment record example |
| contracts/examples/judgment_application_record.json | CREATE | Golden-path judgment application example |
| contracts/examples/judgment_eval_result.json | CREATE | Golden-path judgment eval result example |
| contracts/standards-manifest.json | MODIFY | Pin new contracts and manifest version |
| contracts/schemas/cycle_manifest.schema.json | MODIFY | Add judgment requirement/input/output fields |
| contracts/examples/cycle_manifest.json | MODIFY | Include judgment config and artifact refs |
| spectrum_systems/modules/runtime/judgment_engine.py | CREATE | Deterministic policy registry + precedent retrieval + judgment evaluation engine |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Integrate required judgment gating before promotion |
| tests/test_contracts.py | MODIFY | Add validation coverage for new judgment contracts/examples |
| tests/test_cycle_runner.py | MODIFY | Add integration tests for judgment gating and fail-closed paths |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document judgment flow, registry selection, precedent retrieval, control gating |
| docs/roadmap/system_roadmap.md | MODIFY | Mirror row update with judgment-layer scope |
| docs/roadmaps/system_roadmap.md | MODIFY | Authority roadmap status text updated for judgment layer |
| docs/reviews/autonomous-loop-judgment-layer-status.md | CREATE | Repo-native review/status artifact for this slice |

## Contracts touched
- `judgment_policy`
- `judgment_record`
- `judgment_application_record`
- `judgment_eval_result`
- `cycle_manifest` (additive fields)
- `standards_manifest` version bump

## Tests that must pass after execution
1. `pytest tests/test_contracts.py tests/test_cycle_runner.py tests/test_pqx_judgment_record.py`
2. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not redesign PQX/control architecture.
- Do not remove or replace existing `pqx_judgment_record` artifacts.
- Do not introduce non-deterministic retrieval/vector infrastructure.

## Dependencies
- CTRL-LOOP-01 closed-loop and review/fix re-entry slices already merged.

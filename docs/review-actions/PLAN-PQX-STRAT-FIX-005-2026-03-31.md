# Plan — PQX-STRAT-FIX-005 — 2026-03-31

## Prompt type
PLAN

## Roadmap item
PQX-STRAT-FIX-005 — Roadmap Eligibility Contract Integration Repair

## Objective
Repair all downstream producers/fixtures consuming or emitting roadmap eligibility artifacts so the stricter canonical strategy-aware contract is used end-to-end without weakening fail-closed semantics.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-STRAT-FIX-005-2026-03-31.md | CREATE | Plan-first requirement for multi-file integration repair. |
| tests/test_next_step_decision.py | MODIFY | Update shared eligibility fixture builder to emit canonical strategy-aware eligibility artifacts. |
| tests/test_next_step_decision_policy.py | MODIFY | Update eligibility test helpers to canonical contract shape. |
| tests/test_cycle_runner.py | MODIFY | Update seeded eligibility payloads used in cycle runner happy/fail paths. |
| spectrum_systems/orchestration/next_step_decision.py | MODIFY (if needed) | Minimal consumer updates if strategy fields require explicit propagation. |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY (if needed) | Minimal consumer updates if canonical eligibility handling requires explicit checks. |

## Contracts touched
None (contract shapes remain unchanged; producer/consumer integration only).

## Tests that must pass after execution
1. `pytest tests/test_roadmap_eligibility.py`
2. `pytest tests/test_pqx_backbone.py`
3. `pytest tests/test_next_step_decision.py`
4. `pytest tests/test_next_step_decision_policy.py`
5. `pytest tests/test_cycle_runner.py`
6. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
7. `python scripts/run_contract_enforcement.py`
8. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not roll back strategy gating.
- Do not weaken any roadmap eligibility schema requirements.
- Do not redesign next-step or cycle orchestration architecture.

## Dependencies
- Prior PQX-STRAT-004 contract/schema updates remain in place and authoritative.

# Plan — SRE-03 Replay Contract Boundary Hardening Slice — 2026-03-26

## Prompt type
PLAN

## Roadmap item
SRE-03 replay hardening follow-on (contract-boundary drift remediation)

## Objective
Replay-adjacent builders, consumers, and regression harness paths consistently validate and consume canonical governed artifact contracts without local stale dict assumptions.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SRE-03-REPLAY-CONTRACT-BOUNDARY-HARDENING-2026-03-26.md | CREATE | Required PLAN artifact for this multi-file hardening slice |
| PLANS.md | MODIFY | Register newly created active plan |
| tests/helpers/replay_adjacent_builders.py | CREATE | Shared canonical replay-adjacent test builders to prevent local drift |
| tests/test_error_budget.py | MODIFY | Replace hand-maintained observability_metrics shape with shared canonical builder fixture |
| tests/test_replay_regression_harness.py | MODIFY | Add stale replay_result shape rejection regression test for harness inputs |
| docs/review-actions/REVIEW-SRE-03-REPLAY-CONTRACT-BOUNDARY-HARDENING-2026-03-26.md | CREATE | Record contract-boundary invariants and in-scope/out-of-scope remediation summary |

## Contracts touched
None (consumer/builder alignment only; no schema edits).

## Tests that must pass after execution
1. `pytest tests/test_error_budget.py tests/test_replay_regression_harness.py`
2. `pytest tests/test_contracts.py`
3. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change any JSON schema definitions under `contracts/schemas/`.
- Do not alter replay control-loop execution semantics.
- Do not remediate unrelated contract-boundary audit findings outside replay-adjacent artifacts.
- Do not add feature behavior, fallback restoration, or AI/LLM behavior.

## Dependencies
- docs/review-actions/PLAN-SRE-03-REPLAY-AUTH-SEAM-2026-03-26.md context is available.
- docs/review-actions/PLAN-SRE-03-REPLAY-FIXTURE-ALIGN-2026-03-26.md context is available.

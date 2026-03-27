# Plan — SRE-09 + SRE-10 Integration — 2026-03-27

## Prompt type
PLAN

## Roadmap item
SRE-09/SRE-10 — Error-budget-aware control-loop integration

## Objective
Enforce `error_budget_status` as a first-class replay input in the runtime control loop with deterministic fail-closed validation, budget-prioritized decision mapping, and explicit integration wiring across runtime + tests.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SRE-09-SRE-10-INTEGRATION-2026-03-27.md | CREATE | Required PLAN artifact for multi-file BUILD |
| PLANS.md | MODIFY | Register active SRE-09/SRE-10 integration plan |
| spectrum_systems/modules/runtime/control_loop.py | MODIFY | Enforce replay error-budget input, fail-closed checks, deterministic control-trace timestamping, rolling-window helper |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Incorporate budget status into system response mapping for evaluation control decisions |
| spectrum_systems/modules/runtime/control_integration.py | MODIFY | Ensure explicit error-budget presence before runtime control invocation |
| spectrum_systems/modules/runtime/agent_golden_path.py | MODIFY | Ensure replay_result used for control always carries deterministic error_budget_status wiring |
| contracts/schemas/evaluation_control_decision.schema.json | MODIFY | Extend triggered/rationale enums for explicit budget-governed decision semantics |
| tests/test_control_loop.py | MODIFY | Add fail-closed and budget-path coverage for control loop |
| tests/test_control_integration.py | MODIFY | Add explicit integration failure coverage for missing error_budget_status |
| tests/test_agent_golden_path.py | MODIFY | Assert replay_result artifact emitted in golden path includes error_budget_status |
| tests/test_evaluation_control.py | MODIFY | Add budget warning/exhausted response mapping coverage |

## Contracts touched
- `contracts/schemas/evaluation_control_decision.schema.json` (enum extension for budget-governed triggered/rationale values)

## Tests that must pass after execution
1. `pytest tests/test_evaluation_control.py tests/test_control_loop.py tests/test_control_integration.py tests/test_agent_golden_path.py`
2. `pytest tests/test_contracts.py`
3. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-SRE-09-SRE-10-INTEGRATION-2026-03-27.md`

## Scope exclusions
- Do not introduce new repositories, frameworks, or non-runtime modules.
- Do not refactor unrelated runtime control/enforcement code paths.
- Do not alter replay artifact identities, envelope format, or non-budget governance behavior outside declared files.

## Dependencies
- Existing replay_result, observability_metrics, and error_budget_status contracts must remain authoritative and schema-valid.

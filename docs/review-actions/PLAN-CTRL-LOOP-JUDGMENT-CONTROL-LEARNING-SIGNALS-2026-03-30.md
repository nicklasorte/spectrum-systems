# Plan — CTRL-LOOP-02 Judgment Control Learning Signals Bundle — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-02 (grouped PQX control-layer wiring from judgment learning signals)

## Objective
Wire deterministic learning-signal governance into control decisions by adding judgment error-budget status computation, drift threshold policy evaluation, control-loop integration logic, and escalation artifacts with fail-closed integration coverage.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CTRL-LOOP-JUDGMENT-CONTROL-LEARNING-SIGNALS-2026-03-30.md | CREATE | Required plan-first record for grouped multi-file PQX slice |
| spectrum_systems/modules/runtime/judgment_learning.py | MODIFY | Add deterministic judgment error-budget status and drift-threshold policy evaluation runners |
| spectrum_systems/modules/runtime/control_loop.py | MODIFY | Extend control-loop seam with learning-signal control decision + escalation artifact emission |
| contracts/schemas/judgment_policy.schema.json | MODIFY | Add versioned explicit policy configuration for drift thresholds, calibration bands, and error budgets |
| contracts/examples/judgment_policy.json | MODIFY | Provide concrete policy example with learning-signal control thresholds |
| contracts/schemas/judgment_error_budget_status.schema.json | CREATE | Governed artifact schema for deterministic judgment error-budget status |
| contracts/examples/judgment_error_budget_status.json | CREATE | Golden-path example for judgment_error_budget_status |
| contracts/schemas/judgment_control_escalation_record.schema.json | CREATE | Governed artifact schema for control escalation decisions |
| contracts/examples/judgment_control_escalation_record.json | CREATE | Golden-path example for escalation record |
| contracts/standards-manifest.json | MODIFY | Publish new contracts and schema version bumps |
| tests/test_judgment_learning.py | MODIFY | Add deterministic and fail-closed tests for error-budget and drift-threshold policy evaluation |
| tests/test_control_loop.py | MODIFY | Add integration tests for allow/warn/freeze/block + fail-closed + determinism on learning-signal control path |
| tests/test_contracts.py | MODIFY | Validate new contract examples |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document learning-signal control integration, error budget, drift thresholds, and escalation artifacts |
| docs/roadmap/system_roadmap.md | MODIFY | Mark grouped PQX control-learning slice execution status |

## Contracts touched
- judgment_policy (schema + example update)
- judgment_error_budget_status (new)
- judgment_control_escalation_record (new)
- standards-manifest update for new contract registry entries and version increments

## Tests that must pass after execution
1. `pytest tests/test_judgment_learning.py tests/test_control_loop.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not create a parallel control plane or alternate orchestration path.
- Do not redesign existing judgment/eval/enforcement boundaries.
- Do not introduce probabilistic inference for drift or error-budget logic.
- Do not modify unrelated roadmap rows or contracts outside the declared slice.

## Dependencies
- Existing judgment artifacts (record/application/eval/outcome/calibration/drift) and control-loop seams are already merged and available.

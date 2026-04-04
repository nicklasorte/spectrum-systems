# Plan — BATCH-LTV-B — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-LTV-B — Decision-Quality Control (LT-05 + LT-06 + LT-09)

## Objective
Add deterministic, fail-closed decision-quality budgeting, longitudinal calibration, and judgment promotion gating artifacts/wiring so promotion-sensitive paths are denied or held when decision quality degrades.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-LTV-B-2026-04-04.md | CREATE | Required plan-first artifact for multi-file contract/module/test scope. |
| PLANS.md | MODIFY | Register active BATCH-LTV-B plan. |
| contracts/schemas/decision_quality_budget_status.schema.json | CREATE | New governed contract for LT-05 budget status. |
| contracts/examples/decision_quality_budget_status.json | CREATE | Golden-path example for LT-05 budget status. |
| contracts/schemas/calibration_assessment_record.schema.json | CREATE | New governed contract for LT-06 longitudinal calibration assessment. |
| contracts/examples/calibration_assessment_record.json | CREATE | Golden-path example for LT-06 calibration assessment. |
| contracts/schemas/judgment_promotion_gate_record.schema.json | CREATE | New governed contract for LT-09 judgment promotion hard gate. |
| contracts/examples/judgment_promotion_gate_record.json | CREATE | Golden-path example for LT-09 promotion gate artifact. |
| contracts/schemas/build_summary.schema.json | MODIFY | Surface decision-quality, calibration, and judgment gate refs in operator summary. |
| contracts/schemas/batch_handoff_bundle.schema.json | MODIFY | Carry decision-quality, calibration, and judgment gate refs across batch boundaries. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and schema version bumps. |
| spectrum_systems/modules/runtime/decision_quality_control.py | CREATE | Deterministic LT-05/LT-06/LT-09 evaluators and helpers. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Integrate budget/calibration/gate evaluation into cycle outputs and fail-closed control decisions. |
| spectrum_systems/modules/runtime/capability_readiness.py | MODIFY | Consume decision-quality and calibration signals in readiness posture. |
| spectrum_systems/modules/runtime/roadmap_signal_steering.py | MODIFY | Accept/surface decision-quality and calibration refs in roadmap signal bundle inputs. |
| tests/test_contracts.py | MODIFY | Validate new contract examples. |
| tests/test_contract_enforcement.py | MODIFY | Enforce standards-manifest registration and bumped summary/handoff schema versions. |
| tests/test_decision_quality_control.py | CREATE | Deterministic/fail-closed LT-05/LT-06/LT-09 unit coverage. |
| tests/test_system_cycle_operator.py | MODIFY | Integration assertions for surfaced refs and promotion hardening behavior. |

## Contracts touched
- Add `decision_quality_budget_status` schema/example.
- Add `calibration_assessment_record` schema/example.
- Add `judgment_promotion_gate_record` schema/example.
- Bump/add manifest entries for `build_summary` and `batch_handoff_bundle` if schema surfaces are expanded.

## Tests that must pass after execution
1. `pytest tests/test_decision_quality_control.py tests/test_system_cycle_operator.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`
5. `pytest`

## Scope exclusions
- Do not redesign roadmap execution architecture.
- Do not add any model-driven control authority.
- Do not add unrelated refactors outside declared files.
- Do not expand full judgment reasoning capability beyond required eval linkage/wiring.

## Dependencies
- BATCH-LTV-A artifacts remain authoritative prerequisites for lifecycle/precedent/override evidence consumed by this batch.

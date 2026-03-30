# Plan — CTRL-LOOP Recovery Bridge Slice — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP governed recovery bridge (decision → remediation routing → fix-plan generation)

## Objective
Add deterministic, policy-governed remediation routing and fix-plan artifact generation wired into next-step decision and cycle manifest persistence, without adding fix execution.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/drift_remediation_policy.schema.json | CREATE | Governed remediation policy schema |
| contracts/examples/drift_remediation_policy.json | CREATE | Golden-path remediation policy example |
| data/policy/drift_remediation_policy.json | CREATE | Default runtime remediation policy |
| contracts/schemas/drift_remediation_artifact.schema.json | CREATE | Structured drift remediation artifact contract |
| contracts/examples/drift_remediation_artifact.json | CREATE | Example remediation artifact |
| contracts/schemas/fix_plan_artifact.schema.json | CREATE | Structured fix-plan artifact contract |
| contracts/examples/fix_plan_artifact.json | CREATE | Example fix-plan artifact |
| spectrum_systems/orchestration/drift_remediation.py | CREATE | Remediation policy loading + artifact generation |
| spectrum_systems/orchestration/fix_plan.py | CREATE | Deterministic fix-plan generation |
| spectrum_systems/orchestration/next_step_decision.py | MODIFY | Route blocking decisions into remediation/fix-plan refs |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Persist remediation/fix-plan artifacts and block progression |
| contracts/schemas/next_step_decision_artifact.schema.json | MODIFY | Add minimal remediation reference fields |
| contracts/examples/next_step_decision_artifact.json | MODIFY | Add remediation-aware examples |
| contracts/schemas/cycle_manifest.schema.json | MODIFY | Persist remediation/fix-plan artifact references |
| contracts/examples/cycle_manifest.json | MODIFY | Include remediation/fix-plan reference fields |
| scripts/run_drift_remediation.py | CREATE | CLI for deterministic remediation artifact generation |
| scripts/run_fix_plan.py | CREATE | CLI for deterministic fix-plan artifact generation |
| contracts/standards-manifest.json | MODIFY | Register new contracts/examples and manifest version bump |
| tests/test_drift_remediation.py | CREATE | Remediation policy + artifact deterministic behavior tests |
| tests/test_fix_plan.py | CREATE | Fix-plan deterministic generation tests |
| tests/test_next_step_decision.py | MODIFY | Cover remediation refs on blocking decisions |
| tests/test_cycle_runner.py | MODIFY | Verify remediation persistence + progression block |
| tests/test_contracts.py | MODIFY | Validate new contract examples |
| tests/test_contract_enforcement.py | MODIFY | Ensure standards manifest includes new contracts/examples |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document decision→remediation→fix-plan seam |
| docs/roadmaps/system_roadmap.md | MODIFY | Record recovery-bridge slice completion scope |

## Contracts touched
- New: `drift_remediation_policy`, `drift_remediation_artifact`, `fix_plan_artifact`
- Modified: `next_step_decision_artifact`, `cycle_manifest`, `standards_manifest`

## Tests that must pass after execution
1. `pytest tests/test_drift_remediation.py tests/test_fix_plan.py tests/test_next_step_decision.py tests/test_cycle_runner.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement fix execution.
- Do not implement remediation approval/certification completion.
- Do not add replay-after-repair logic.
- Do not redesign control-loop state machine beyond minimal wiring fields.

## Dependencies
- Existing next-step decision policy seam and cycle runner governance enforcement must remain intact.
- Strategy/source authority contracts and enforcement remain authoritative.

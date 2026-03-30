# Plan — CTRL-LOOP-05 Lifecycle Enforcement Hardening — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-05

## Objective
Make lifecycle + rollout evidence mandatory on governed cycle/control/runtime policy-selection paths, propagate lifecycle linkage through downstream enforcement artifacts, and prove fail-closed behavior with end-to-end integration tests.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CTRL-LOOP-05-LIFECYCLE-ENFORCEMENT-HARDENING-2026-03-30.md | CREATE | Required PLAN artifact before grouped multi-file BUILD work |
| PLANS.md | MODIFY | Register active PLAN entry |
| contracts/schemas/cycle_manifest.schema.json | MODIFY | Add governed lifecycle/rollout path declarations for runtime wiring |
| contracts/schemas/judgment_application_record.schema.json | MODIFY | Add lifecycle linkage fields for governed decision traceability |
| contracts/schemas/judgment_control_escalation_record.schema.json | MODIFY | Add selected policy version + lifecycle/rollout linkage in control trace |
| contracts/schemas/judgment_enforcement_action_record.schema.json | MODIFY | Add lifecycle linkage in downstream enforcement policy refs |
| contracts/schemas/judgment_enforcement_outcome_record.schema.json | MODIFY | Add lifecycle linkage in enforcement outcome trace |
| contracts/examples/cycle_manifest.json | MODIFY | Golden-path example with lifecycle and rollout artifact refs |
| contracts/examples/judgment_application_record.json | MODIFY | Golden-path linkage example |
| contracts/examples/judgment_control_escalation_record.json | MODIFY | Golden-path control linkage example |
| contracts/examples/judgment_enforcement_action_record.json | MODIFY | Golden-path enforcement linkage example |
| contracts/examples/judgment_enforcement_outcome_record.json | MODIFY | Golden-path outcome linkage example |
| contracts/standards-manifest.json | MODIFY | Publish contract version bumps and standards version increment |
| spectrum_systems/modules/runtime/judgment_engine.py | MODIFY | Enforce strict governed lifecycle/rollout selection and propagate linkage |
| spectrum_systems/modules/runtime/control_loop.py | MODIFY | Include lifecycle linkage in escalation trace |
| spectrum_systems/modules/runtime/judgment_enforcement.py | MODIFY | Preserve lifecycle linkage in enforcement artifacts |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Make governed runtime path require lifecycle/rollout artifacts and pass through |
| tests/test_cycle_runner.py | MODIFY | Add governed end-to-end fail-closed + linkage integration tests |
| tests/test_judgment_policy_lifecycle.py | MODIFY | Cover strict selection semantics for deprecated/revoked/lifecycle/rollout |
| tests/test_contracts.py | MODIFY | Validate updated examples/contracts |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document mandatory strict lifecycle behavior and lifecycle-link propagation |
| docs/roadmap/system_roadmap.md | MODIFY | Update CTRL-LOOP-05 row with mandatory enforcement status |

## Contracts touched
- `cycle_manifest`
- `judgment_application_record`
- `judgment_control_escalation_record`
- `judgment_enforcement_action_record`
- `judgment_enforcement_outcome_record`
- `standards_manifest`

## Tests that must pass after execution
1. `pytest tests/test_cycle_runner.py tests/test_judgment_policy_lifecycle.py tests/test_contracts.py`
2. `python scripts/run_contract_enforcement.py`
3. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign cycle state machine.
- Do not introduce a parallel policy plane.
- Do not refactor unrelated runtime modules outside lifecycle/control/enforcement seams.

## Dependencies
- Existing CTRL-LOOP-05 lifecycle artifacts and selection seam are treated as prerequisites.

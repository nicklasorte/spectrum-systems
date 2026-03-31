# Plan — G11 Cycle Manifest Source of Truth Hardening — 2026-03-31

## Prompt type
PLAN

## Roadmap item
G11 — one-loop control determinism hardening (manifest supremacy slice)

## Objective
Make `cycle_manifest` the single deterministic, fail-closed, schema-enforced authority linking roadmap, eligibility, decision, and selected-step execution authorization.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-G11-CYCLE-MANIFEST-SOURCE-OF-TRUTH-2026-03-31.md | CREATE | Required PLAN artifact before multi-file BUILD execution. |
| contracts/schemas/cycle_manifest.schema.json | MODIFY | Harden contract with required decision trace fields and stricter manifest authority semantics. |
| contracts/examples/cycle_manifest.json | MODIFY | Keep golden-path example aligned with hardened schema and traceability fields. |
| contracts/standards-manifest.json | MODIFY | Version bump and registry update for cycle manifest contract changes. |
| spectrum_systems/orchestration/cycle_manifest_validator.py | CREATE | Add reusable schema + semantic validator for cycle manifest fail-closed checks. |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Enforce pre/post manifest validation, deterministic enrichment, eligibility-authorized selection-only progression. |
| spectrum_systems/orchestration/next_step_decision.py | MODIFY | Ensure decision artifact traceability fields remain explicit and deterministic. |
| scripts/run_cycle_manifest_validation.py | CREATE | CLI validator entrypoint with non-zero exit on schema/semantic failures. |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document cycle manifest as source of truth and artifact-driven replay model. |
| tests/test_cycle_manifest.py | CREATE | Add schema + semantic validation tests for hardened manifest contract/validator. |
| tests/test_cycle_runner.py | MODIFY | Add/adjust tests for manifest enrichment, fail-closed decision checks, and selected-step authorization semantics. |
| tests/test_next_step_decision.py | MODIFY | Assert decision artifact includes required eligibility linkage and deterministic snapshots. |

## Contracts touched
- `contracts/schemas/cycle_manifest.schema.json` (version bump + additive required decision-trace fields)
- `contracts/standards-manifest.json` (registry update for cycle manifest schema version)

## Tests that must pass after execution
1. `pytest tests/test_cycle_manifest.py`
2. `pytest tests/test_cycle_runner.py`
3. `pytest tests/test_next_step_decision.py`
4. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
5. `python scripts/run_contract_enforcement.py`
6. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add parallel orchestration layers or alternate state containers.
- Do not modify PQX runtime adapters beyond selected-step authorization linkage already present in control artifacts.
- Do not redesign roadmap authoring flow or eligibility generation logic.

## Dependencies
- Existing `roadmap_eligibility_artifact` and `next_step_decision_artifact` contracts remain authoritative producer/consumer inputs.
- Existing control-loop state machine in `cycle_runner` remains the execution progression backbone.

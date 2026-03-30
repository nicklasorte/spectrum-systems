# Plan — PQX Roadmap Eligibility Seam — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-01 follow-on hard gate — roadmap eligibility seam

## Objective
Add a deterministic, fail-closed, schema-bound roadmap eligibility artifact and evaluator that separates roadmap planning from execution permission while preserving one-step-at-a-time control supremacy.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-ROADMAP-ELIGIBILITY-2026-03-30.md | CREATE | Required PLAN artifact before multi-file contract/orchestration changes |
| contracts/schemas/governed_roadmap_artifact.schema.json | CREATE | Contract-first input schema for deterministic eligibility evaluation |
| contracts/examples/governed_roadmap_artifact.json | CREATE | Golden-path governed roadmap example with eligibility metadata |
| contracts/schemas/roadmap_eligibility_artifact.schema.json | CREATE | New strict eligibility artifact contract |
| contracts/examples/roadmap_eligibility_artifact.json | CREATE | Golden-path eligibility artifact example |
| contracts/standards-manifest.json | MODIFY | Register new contracts and bump standards version |
| spectrum_systems/orchestration/roadmap_eligibility.py | CREATE | Deterministic fail-closed evaluator implementation |
| spectrum_systems/orchestration/__init__.py | MODIFY | Export roadmap eligibility evaluator seam |
| scripts/run_roadmap_eligibility.py | CREATE | Thin CLI for evaluation + schema validation + fail-closed exit codes |
| tests/test_roadmap_eligibility.py | CREATE | Eligibility logic + determinism + fail-closed + CLI coverage |
| tests/test_contracts.py | MODIFY | Validate new examples against new schemas |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Minimal architecture lock for planning vs eligibility vs control boundaries |

## Contracts touched
- `contracts/schemas/governed_roadmap_artifact.schema.json` (new)
- `contracts/schemas/roadmap_eligibility_artifact.schema.json` (new)
- `contracts/standards-manifest.json` version bump and contract registration

## Tests that must pass after execution
1. `pytest tests/test_roadmap_eligibility.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not rewire `next_step_decision` to require eligibility artifact in this slice.
- Do not add or enable parallel execution.
- Do not modify PQX execution semantics.
- Do not redesign roadmap markdown/planner workflow.

## Dependencies
- Existing control-loop foundations in `spectrum_systems/orchestration/cycle_runner.py` and `next_step_decision.py` must remain authoritative for execution gating.

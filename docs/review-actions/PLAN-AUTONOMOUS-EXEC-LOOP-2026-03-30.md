# Plan — Autonomous Execution Loop Foundation — 2026-03-30

## Prompt type
PLAN

## Roadmap item
AUTONOMOUS-LOOP-FDN-01

## Objective
Implement a deterministic, fail-closed control-plane foundation for cycle orchestration, review artifacts, fix-roadmap generation, and certification handoff seams.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-AUTONOMOUS-EXEC-LOOP-2026-03-30.md | CREATE | Required multi-file execution plan |
| PLANS.md | MODIFY | Register new active plan |
| contracts/schemas/cycle_manifest.schema.json | CREATE | Contract-first cycle state artifact |
| contracts/schemas/roadmap_review_artifact.schema.json | CREATE | Contract for roadmap review outputs |
| contracts/schemas/execution_report_artifact.schema.json | CREATE | Contract for execution report outputs |
| contracts/schemas/implementation_review_artifact.schema.json | CREATE | Contract for implementation review outputs |
| contracts/schemas/fix_roadmap_artifact.schema.json | CREATE | Contract for generated fix roadmap |
| contracts/examples/cycle_manifest.json | CREATE | Golden-path cycle manifest example |
| contracts/examples/roadmap_review_artifact.json | CREATE | Golden-path roadmap review example |
| contracts/examples/execution_report_artifact.json | CREATE | Golden-path execution report example |
| contracts/examples/implementation_review_artifact.json | CREATE | Golden-path implementation review example |
| contracts/examples/fix_roadmap_artifact.json | CREATE | Golden-path fix roadmap example |
| contracts/standards-manifest.json | MODIFY | Publish contract versions and entries |
| spectrum_systems/orchestration/__init__.py | CREATE | Orchestration package export |
| spectrum_systems/orchestration/cycle_runner.py | CREATE | Deterministic fail-closed cycle runner |
| spectrum_systems/fix_engine/__init__.py | CREATE | Fix engine package export |
| spectrum_systems/fix_engine/generate_fix_roadmap.py | CREATE | Deterministic fix roadmap generator |
| runs/cycle-0001/cycle_manifest.json | CREATE | Repo-native cycle manifest template |
| docs/roadmap/system_roadmap.md | MODIFY | Compatibility mirror row for autonomous loop slice |
| docs/roadmap/fix_roadmap.md | CREATE | Human-readable generated fix roadmap surface |
| docs/reviews/roadmap_review_template.md | CREATE | Roadmap review template |
| docs/reviews/implementation_review_claude_template.md | CREATE | Claude implementation review template |
| docs/reviews/implementation_review_codex_template.md | CREATE | Codex implementation review template |
| docs/architecture/autonomous_execution_loop.md | CREATE | Concise architecture note |
| docs/runbooks/cycle_runner.md | CREATE | Operator runbook |
| tests/fixtures/autonomous_cycle/roadmap_review_approved.json | CREATE | Deterministic roadmap review fixture |
| tests/fixtures/autonomous_cycle/implementation_review_claude.json | CREATE | Deterministic implementation review fixture |
| tests/fixtures/autonomous_cycle/implementation_review_codex.json | CREATE | Deterministic implementation review fixture |
| tests/test_cycle_runner.py | CREATE | Cycle state/runner fail-closed tests |
| tests/test_fix_roadmap_generator.py | CREATE | Fix-roadmap deterministic grouping tests |

## Contracts touched
- `cycle_manifest`
- `roadmap_review_artifact`
- `execution_report_artifact`
- `implementation_review_artifact`
- `fix_roadmap_artifact`
- `contracts/standards-manifest.json` (version + entries)

## Tests that must pass after execution
1. `pytest tests/test_cycle_runner.py tests/test_fix_roadmap_generator.py`
2. `pytest tests/test_contracts.py`
3. `pytest tests/test_module_architecture.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not implement a full PQX execution engine.
- Do not implement live Claude/Codex RPC integrations.
- Do not redesign existing prompt queue or runtime orchestration modules.
- Do not implement full done-certification internals beyond handoff seam reuse.

## Dependencies
- Existing GOV-10 seam (`spectrum_systems/modules/governance/done_certification.py`) must remain authoritative for certification execution.

# Plan — BATCH-GOV-01 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-GOV-01 — Wire Strategy Control into Spectrum Systems

## Objective
Activate strategy governance as an explicit, reusable, machine-readable input layer across roadmap generation, architecture review, and implementation prompts.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GOV-01-2026-04-07.md | CREATE | Required plan artifact before multi-file governance wiring |
| docs/governance/strategy_control_doc.md | CREATE | Establish governance-path canonical strategy authority document required by this slice |
| docs/governance/README.md | CREATE | Governance layer purpose, authority model, and usage boundaries |
| docs/governance/governance_manifest.json | CREATE | Machine-readable governance authority/workflow mapping |
| docs/governance/prompt_includes/roadmap_governance_include.md | CREATE | Reusable governance include for roadmap prompts |
| docs/governance/prompt_includes/implementation_governance_include.md | CREATE | Reusable governance include for implementation prompts |
| docs/governance/architecture_review_checklist.md | CREATE | Practical architecture review governance checklist |
| docs/governance/prompt_contract.md | CREATE | Mandatory prompt loading contract for governance-critical prompts |
| docs/governance/drift_signals.md | CREATE | Operational drift severity signal reference and response model |
| docs/governance/GOVERNANCE_INTEGRATION_BACKLOG.md | CREATE | Dependency-aware next-step governance integration backlog |

## Contracts touched
None.

## Tests that must pass after execution
1. `test -f docs/governance/README.md && test -f docs/governance/governance_manifest.json && test -f docs/governance/prompt_includes/roadmap_governance_include.md && test -f docs/governance/prompt_includes/implementation_governance_include.md && test -f docs/governance/architecture_review_checklist.md && test -f docs/governance/prompt_contract.md && test -f docs/governance/drift_signals.md && test -f docs/governance/GOVERNANCE_INTEGRATION_BACKLOG.md && test -f docs/governance/strategy_control_doc.md`
2. `python -m json.tool docs/governance/governance_manifest.json >/dev/null`
3. `rg -n "docs/governance/strategy_control_doc.md" docs/governance/README.md docs/governance/governance_manifest.json docs/governance/prompt_includes/roadmap_governance_include.md docs/governance/prompt_includes/implementation_governance_include.md docs/governance/architecture_review_checklist.md docs/governance/prompt_contract.md docs/governance/drift_signals.md docs/governance/GOVERNANCE_INTEGRATION_BACKLOG.md`
4. `PLAN_FILES="docs/review-actions/PLAN-BATCH-GOV-01-2026-04-07.md docs/governance/strategy_control_doc.md docs/governance/README.md docs/governance/governance_manifest.json docs/governance/prompt_includes/roadmap_governance_include.md docs/governance/prompt_includes/implementation_governance_include.md docs/governance/architecture_review_checklist.md docs/governance/prompt_contract.md docs/governance/drift_signals.md docs/governance/GOVERNANCE_INTEGRATION_BACKLOG.md" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign runtime modules, contracts, or CI enforcement engines.
- Do not modify roadmap contents outside governance activation references.
- Do not change strategy meaning beyond path activation and formatting-safe carryover.

## Dependencies
- Existing strategy governance architecture references under `docs/architecture/strategy-control.md`.

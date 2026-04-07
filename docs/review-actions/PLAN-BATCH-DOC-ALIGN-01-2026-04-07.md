# Plan — BATCH-DOC-ALIGN-01 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-DOC-ALIGN-01

## Objective
Align high-impact governance Markdown files so Codex and Claude consume one explicit, non-contradictory operating model.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| CLAUDE.md | MODIFY | Replace conflicting/legacy guidance with concise role-specific governed-runtime instructions. |
| CODEX.md | MODIFY | Align execution-agent instructions with canonical runtime rules and terminology. |
| AGENTS.md | MODIFY | Remove ambiguity and align root operating rules with canonical sources and governance terms. |
| docs/governance/prompt_contract.md | MODIFY | Define concise prompt contract with explicit required inputs and fail-closed behavior. |
| docs/governance/prompt_execution_rules.md | MODIFY | Normalize execution preflight and failure handling language. |
| docs/governance/strategy_control_doc.md | MODIFY | Keep strategy controls explicit, minimal, and consistent with canonical sources. |
| docs/governance/governed_prompt_surfaces.md | MODIFY | Provide single authoritative inventory of governed prompt surfaces and ownership. |
| docs/level-0-to-20-playbook.md | MODIFY | Mark as archived/non-active guidance. |
| docs/automation_maturity_model.md | MODIFY | Mark as archived/non-active guidance. |
| docs/100-step-roadmap.md | MODIFY | Mark as archived/non-active guidance. |
| docs/review-actions/PLAN-BATCH-DOC-ALIGN-01-2026-04-07.md | CREATE | Record required PLAN before multi-file BUILD scope. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python -m compileall scripts` (sanity check that no runtime code touched; command expected to pass in this repo)
2. `.codex/skills/verify-changed-scope/run.sh`
3. `git diff --name-only`

## Scope exclusions
- Do not modify runtime code, schemas, or contracts.
- Do not change README.md or docs/architecture/system_registry.md content in this batch.
- Do not introduce new architecture or new subsystem roles.

## Dependencies
- None.

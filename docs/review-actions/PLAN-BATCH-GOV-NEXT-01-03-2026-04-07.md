# Plan — BATCH-GOV-NEXT-01-03 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-GOV-NEXT-01-03

## Objective
Enforce fail-closed governance loading for roadmap, implementation, and architecture-review prompt seams via reusable templates and lightweight preflight tooling.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GOV-NEXT-01-03-2026-04-07.md | CREATE | Required PLAN artifact before multi-file BUILD work |
| docs/governance/source_inputs_manifest.json | CREATE | Add required governance source-input authority manifest consumed by prompt seams |
| docs/governance/prompt_includes/source_input_loading_include.md | CREATE | Provide reusable source-loading include required by prompt preflight |
| docs/governance/prompt_includes/ENFORCED_PREAMBLE.md | CREATE | Add fail-closed governance preamble for prompt execution |
| docs/governance/prompt_templates/roadmap_prompt_template.md | CREATE | Enforced roadmap prompt composition template |
| docs/governance/prompt_templates/implementation_prompt_template.md | CREATE | Enforced implementation prompt composition template |
| docs/governance/prompt_templates/architecture_review_prompt_template.md | CREATE | Enforced architecture review prompt composition template |
| scripts/check_governance_compliance.py | CREATE | Lightweight fail-closed governance prompt preflight checker |
| scripts/run_prompt_with_governance.py | CREATE | Wrapper that runs governance preflight prior to prompt execution |
| docs/governance/prompt_execution_rules.md | CREATE | Execution policy and remediation guidance for fail-closed prompting |
| tests/test_governance_prompt_enforcement.py | CREATE | Deterministic tests for governance prompt preflight enforcement |
| docs/governance/governance_manifest.json | MODIFY | Register enforcement mechanisms, required prompt inputs, preflight checks, and templates |
| docs/governance/README.md | MODIFY | Document fail-closed enforcement model, templates, and checker usage |
| prompts/prompt-template.md | MODIFY | Wire generic prompt seam to enforced governance preamble + templates |
| templates/review/claude_review_prompt_template.md | MODIFY | Wire architecture review prompt seam to enforced governance preamble |

## Contracts touched
None.

## Tests that must pass after execution
1. `python -m pytest tests/test_governance_prompt_enforcement.py`
2. `python scripts/check_governance_compliance.py --file docs/governance/prompt_templates/roadmap_prompt_template.md`
3. `python scripts/check_governance_compliance.py --text "# Invalid prompt\nOnly arbitrary content"`

## Scope exclusions
- Do not introduce new runtime services or orchestration frameworks.
- Do not modify contracts in `contracts/schemas/`.
- Do not alter roadmap policy authority in `docs/roadmaps/system_roadmap.md`.
- Do not refactor unrelated scripts or test suites.

## Dependencies
- `docs/governance/strategy_control_doc.md` and existing governance includes must remain authoritative inputs.

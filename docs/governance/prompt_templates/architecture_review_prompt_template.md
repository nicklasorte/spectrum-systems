# Architecture Review Prompt Template (Governance Enforced)

## Enforced Preamble Include
- `docs/governance/prompt_includes/ENFORCED_PREAMBLE.md`
- `docs/governance/prompt_includes/source_input_loading_include.md`
- `docs/governance/prompt_includes/implementation_governance_include.md`

## Inputs
- `docs/governance/strategy_control_doc.md`
- `docs/governance/source_inputs_manifest.json`
- `docs/governance/architecture_review_checklist.md`
- review scope files, contracts, and validation evidence

## Constraints
- Missing governance sources are blocking defects.
- Validate no agent-first or prompt-first drift.
- Block findings that allow eval/control/replay/certification bypass.
- Enforce foundation-before-expansion in review recommendations.

## Task
Assess the scoped architecture against governance invariants and produce a bounded review outcome.

## Output requirements
- Include loaded-source evidence list.
- Provide severity-ranked findings with governance invariant references.
- Emit explicit NO_GO / blocking outcome when fail-closed preflight is not satisfied.

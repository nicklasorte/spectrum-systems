# Implementation Prompt Template (Governance Enforced)

## Enforced Preamble Include
- `docs/governance/prompt_includes/ENFORCED_PREAMBLE.md`
- `docs/governance/prompt_includes/source_input_loading_include.md`
- `docs/governance/prompt_includes/implementation_governance_include.md`

## Inputs
- `docs/governance/strategy_control_doc.md`
- `docs/governance/source_inputs_manifest.json`
- `docs/governance/prompt_contract.md`
- relevant implementation scope files and contracts

## Constraints
- Fail closed when any governance input is missing.
- Preserve strategy/control invariants.
- No hidden contracts or undeclared schema coupling.
- No bypasses around eval, control, replay, trace, or certification.

## Task
Implement the scoped capability while preserving governance constraints and declared scope boundaries.

## Output requirements
- Enumerate loaded governance inputs.
- List changed files, invariants preserved, and failure modes.
- Identify control-loop and observability impacts.
- Return explicit blocking defect if governance preflight fails.

# Roadmap Prompt Template (Governance Enforced)

## Enforced Preamble Include
- `docs/governance/prompt_includes/ENFORCED_PREAMBLE.md`
- `docs/governance/prompt_includes/source_input_loading_include.md`
- `docs/governance/prompt_includes/roadmap_governance_include.md`

## Inputs
- `docs/governance/strategy_control_doc.md`
- `docs/governance/source_inputs_manifest.json`
- current roadmap authority (`docs/roadmaps/system_roadmap.md`)
- repository state and scoped evidence artifacts

## Constraints
- Fail closed on missing governance input.
- Foundation-before-expansion sequencing is mandatory.
- Reject agent-first/prompt-first recommendations.
- No eval/control/replay/certification bypass proposals.

## Task
Generate or revise roadmap sequencing decisions grounded in loaded governance inputs.
If blocking drift exists, prioritize corrective/hardening steps before expansion rows.

## Output requirements
- Provide explicit loaded-source list.
- Provide blocking failures if governance inputs are missing.
- Emit structured roadmap output with trust gain, invariant guard, and control-loop linkage per step.

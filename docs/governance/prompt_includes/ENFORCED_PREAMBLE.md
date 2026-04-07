# Enforced Governance Preamble (Fail-Closed)

Use this block at the top of any roadmap, implementation, or architecture-review prompt.

## Mandatory loaded inputs
- `docs/governance/strategy_control_doc.md`
- `docs/governance/source_inputs_manifest.json`
- `docs/governance/prompt_includes/source_input_loading_include.md`
- exactly one context include:
  - `docs/governance/prompt_includes/roadmap_governance_include.md`, or
  - `docs/governance/prompt_includes/implementation_governance_include.md`

## Fail-closed gate
If any mandatory input above is missing, unresolved, or not explicitly loaded:
**STOP IMMEDIATELY. DO NOT CONTINUE. DO NOT PRODUCE OUTPUT.**

## Enforced governance constraints
- No agent-first drift: do not prioritize agent expansion ahead of control/foundation closure.
- No prompt-first logic: prompts cannot invent policy authority outside loaded governance sources.
- No bypasses: never bypass eval, control, replay, or certification obligations.
- Foundation-before-expansion: unresolved foundation/control gaps block expansion proposals.

## Copy-paste prompt header block
```text
[GOVERNANCE PRECHECK — FAIL-CLOSED]
Load required governance inputs before any analysis:
1) docs/governance/strategy_control_doc.md
2) docs/governance/source_inputs_manifest.json
3) docs/governance/prompt_includes/source_input_loading_include.md
4) docs/governance/prompt_includes/roadmap_governance_include.md OR docs/governance/prompt_includes/implementation_governance_include.md

If any required governance input is missing: STOP. Return only a blocking error that lists missing inputs.

Enforce: no agent-first drift, no prompt-first logic, no eval/control/replay/certification bypass, foundation-before-expansion.
```

# Source Input Loading Include (Reusable)

> Mandatory include for governed prompts that can alter roadmap direction, architecture assessment outcomes, or implementation behavior.

## Required source-loading sequence
1. `docs/governance/strategy_control_doc.md`
2. `docs/governance/source_inputs_manifest.json`
3. applicable governance include(s):
   - roadmap prompt: `docs/governance/prompt_includes/roadmap_governance_include.md`
   - implementation/review prompt: `docs/governance/prompt_includes/implementation_governance_include.md`

## Fail-closed loading rule
If any required source is unavailable, stale, or omitted, the prompt run is invalid and must stop before analysis, planning, or execution output.

## Loading evidence requirement
Prompt outputs must enumerate loaded source paths and clearly mark any blocked/missing source as a stop condition.

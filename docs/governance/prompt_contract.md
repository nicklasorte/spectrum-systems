# Governance Prompt Contract

## Contract purpose
Define mandatory governance-loading behavior for prompts that can alter roadmap direction, control integrity, trust posture, or promotion outcomes.

## Mandatory prompts
Any prompt touching one or more of the following **must** load governance authority inputs before analysis or execution:
- roadmap generation or roadmap ordering,
- architecture changes affecting control/eval/policy/trace/certification,
- control-loop behavior,
- evaluation policy or enforcement,
- governance or promotion decisions,
- significant execution-flow changes with trust impact.

### Required inputs for mandatory prompts
1. `docs/governance/strategy_control_doc.md`
2. Relevant include(s):
   - roadmap work: `docs/governance/prompt_includes/roadmap_governance_include.md`
   - implementation work: `docs/governance/prompt_includes/implementation_governance_include.md`
3. Optional but recommended context from `docs/governance/governance_manifest.json`

## Optional prompts
Prompts that are purely editorial, typo fixes, or non-governance local docs updates may skip mandatory governance includes **if** they do not alter execution, architecture authority, or policy semantics.

## Prohibited behavior
- Running governance-critical prompts without loading `docs/governance/strategy_control_doc.md`.
- Introducing alternate authority ordering without explicit supersession/ADR.
- Expanding capability while unresolved blocking drift or foundational control gaps remain.
- Creating implicit policy logic that is not represented in declared governance artifacts.

## Drift definition for prompt operations
Prompt-level drift includes:
- authority omission,
- authority reordering,
- invariant softening,
- bypass-accepting outputs,
- expansion recommendations that ignore unresolved earlier foundational slices.

When drift is detected, the prompt must shift to corrective/foundation output mode and block expansion recommendations.

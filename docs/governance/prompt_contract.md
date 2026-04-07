# Prompt Contract

## Purpose
Define the mandatory contract for governance-impacting prompts.

## Applies to
Any prompt that can change execution behavior, promotion outcomes, control boundaries, or system-role ownership.

## Required authority inputs
A compliant prompt must explicitly include:
1. `README.md`
2. `docs/architecture/system_registry.md`
3. `docs/governance/strategy_control_doc.md`
4. One execution include:
   - `docs/governance/prompt_includes/roadmap_governance_include.md`, or
   - `docs/governance/prompt_includes/implementation_governance_include.md`

## Contract requirements
- Preserve artifact-first execution.
- Preserve fail-closed behavior.
- Preserve certification-gated promotion.
- Preserve canonical role ownership (`RIL`, `CDE`, `TLC`, `PQX`, `FRE`, `SEL`, `PRG`).

## Failure handling
If any required authority input is missing, the prompt is invalid and must not execute.
Execution resumes only after the missing input is added and validation passes.

## Prohibited behavior
- Implicit workflow shortcuts.
- Redefining system role ownership outside the system registry.
- Using archived maturity-model documents as active instruction sources.

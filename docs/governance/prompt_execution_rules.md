# Prompt Execution Rules (Fail-Closed Governance)

## Enforcement policy
All roadmap, implementation, and architecture-review prompts must pass governance preflight checks before execution.
Missing governance references are blocking defects.

## Required governance references in a valid prompt
A prompt is valid only if it references all of the following:
- `docs/governance/strategy_control_doc.md`
- `docs/governance/source_inputs_manifest.json`
- `docs/governance/prompt_includes/source_input_loading_include.md`
- at least one governance include:
  - `docs/governance/prompt_includes/roadmap_governance_include.md`, or
  - `docs/governance/prompt_includes/implementation_governance_include.md`

## How to run preflight checks
- Check prompt file:
  - `python scripts/check_governance_compliance.py --file <prompt_file>`
- Check prompt text directly:
  - `python scripts/check_governance_compliance.py --text "<prompt_text>"`
- Run wrapper with preflight:
  - `python scripts/run_prompt_with_governance.py <prompt_file>`

## Failure handling
If preflight fails:
1. Read missing items from checker output.
2. Add missing governance references to the prompt.
3. Re-run checker until PASS.
4. Do not execute prompt until preflight returns exit code 0.

## Blocking-defect rule
Any prompt execution that proceeds after a failed preflight is non-compliant and must be treated as a blocking governance defect requiring immediate remediation.

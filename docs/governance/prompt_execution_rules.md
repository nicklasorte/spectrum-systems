# Prompt Execution Rules

## Purpose
Define fail-closed prompt preflight and execution behavior.

## Preflight requirements
Before execution, a prompt must reference:
1. `README.md`
2. `docs/architecture/system_registry.md`
3. `docs/governance/strategy_control_doc.md`
4. `docs/governance/prompt_contract.md`
5. One include:
   - `docs/governance/prompt_includes/roadmap_governance_include.md`, or
   - `docs/governance/prompt_includes/implementation_governance_include.md`

## Preflight command
`python scripts/check_governance_compliance.py --file <prompt_file>`

## Execution rules
- If preflight fails, execution is blocked.
- If required authority is missing, execution is blocked.
- If role ownership conflicts with `docs/architecture/system_registry.md`, execution is blocked.
- Promotion actions require certification evidence artifacts.

## Failure recovery
1. Retrieve missing references from preflight output.
2. Update the prompt.
3. Re-run preflight until pass.
4. Execute only after pass.

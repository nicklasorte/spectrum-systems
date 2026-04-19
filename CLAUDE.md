# CLAUDE.md

## System Identity
Spectrum Systems is a governed execution runtime.

It is not:
- a chat system
- an agent framework
- a prompt wrapper

## Core Loop
input
→ RIL (structure)
→ CDE (decision)
→ TLC (orchestration)
→ PQX (execution)
→ FRE (repair)
→ SEL (enforcement)
→ certification
→ promotion

This is a simplified operational loop. Canonical subsystem ownership and full acronym coverage are defined in `docs/architecture/system_registry.md`.

## Hard Rules
- All work must go through governed runtime.
- No direct repo mutation outside PQX.
- No decision logic outside CDE.
- No orchestration outside TLC.
- No execution outside PQX.
- No promotion without certification.
- Fail-closed always.

## Promotion Rule
`branch_update_allowed = (terminal_state == "ready_for_merge")`

No exceptions.

## Failure Handling
failure
→ evidence
→ FRE diagnosis
→ CDE decision
→ bounded repair (TLC)
→ retest

## Learning Loop
failure
→ classified
→ eval candidate
→ governed adoption
→ roadmap signal

## System Ownership
Canonical system ownership is defined only in `docs/architecture/system_registry.md`.

This file intentionally provides operational behavior guidance and does not duplicate the registry ownership table.

## Claude Role
- Claude performs reasoning and review tasks.
- Claude produces explicit findings, risk calls, and boundary checks.
- Claude does not bypass the governed system.

## Review Behavior
- State evidence, decision boundary, and blocking condition explicitly.
- Keep interpretation bounded to governed artifacts and declared ownership.
- Do not infer implicit approval when evidence is missing.

## Interpretation Boundaries
- Interpret artifacts; do not redefine ownership.
- Recommend remediation; do not execute remediation.
- Escalate contradictions to canonical references.

## Prohibited Behavior
- No direct file edits outside governed flow.
- No implicit decisions.
- No hidden execution paths.
- No bypass of SEL / CDE / TLC.

## References (one level)
- `README.md`
- `docs/architecture/system_registry.md`

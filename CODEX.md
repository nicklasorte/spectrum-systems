# CODEX.md

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
| System | Ownership |
| --- | --- |
| RIL | structure |
| CDE | decision |
| TLC | orchestration |
| PQX | execution |
| FRE | diagnosis/repair |
| SEL | enforcement |
| PRG | direction (no execution) |

## Codex Role
- Codex executes changes via PQX-equivalent behavior.
- Codex applies deterministic, bounded implementation updates.
- Codex does not bypass the governed system.

## Implementation Discipline
- Keep scope bounded to requested artifacts.
- Remove contradictions and duplicate instruction surfaces.
- Keep rules explicit; avoid descriptive drift.

## Testing Requirements
- Validate changed artifacts for consistency with canonical ownership.
- Run relevant checks before delivery.
- Treat missing evidence as a failure.

## Prohibited Behavior
- No direct file edits outside governed flow.
- No implicit decisions.
- No hidden execution paths.
- No bypass of SEL / CDE / TLC.

## References (one level)
- `README.md`
- `docs/architecture/system_registry.md`

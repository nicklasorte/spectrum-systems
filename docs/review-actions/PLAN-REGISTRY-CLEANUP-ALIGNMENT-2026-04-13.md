# Plan — REGISTRY-CLEANUP-ALIGNMENT — 2026-04-13

## Prompt type
PLAN

## Roadmap item
Unscheduled governance correction (registry authority hardening)

## Objective
Make `docs/architecture/system_registry.md` internally canonical and propagate those ownership boundaries across repository governance surfaces with fail-closed consistency.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/architecture/system_registry.md | MODIFY | Remove duplicate/overlapping systems, harden canonical ownership, align graphs/tables/extensions. |
| docs/architecture/*.md | MODIFY | Rewrite stale ownership references to canonical owners. |
| docs/reviews/**/*.md | MODIFY | Add registry alignment notes and remove active references to removed systems. |
| docs/roadmaps/**/*.md | MODIFY | Replace stale owner assignments with canonical owners. |
| docs/design/**/*.md | MODIFY | Align diagrams and ownership language to canonical registry boundaries. |
| contracts/** | MODIFY | Update or annotate removed-system identifiers where safe. |
| schemas/** | MODIFY | Update or annotate removed-system identifiers where safe. |
| manifests/** | MODIFY | Update stale owner metadata and mappings. |
| tests/** | MODIFY | Update references to removed systems or add canonical mapping comments. |
| scripts/** | MODIFY | Update owner constants/messages to canonical mappings. |

## Contracts touched
None planned; only naming/ownership alignment edits unless incidental annotations are needed.

## Tests that must pass after execution
1. `python scripts/validate_system_registry.py`
2. `rg -n "\b(CLX|JDG|CAN|TAX|CAX|CPX|HFX)\b" docs/architecture docs/design docs/roadmaps docs/reviews contracts schemas manifests tests scripts`
3. `git diff --check`

## Scope exclusions
- Do not introduce new architecture systems beyond canonical cleanup requirements.
- Do not refactor unrelated code paths outside ownership/reference alignment.
- Do not alter runtime behavior code unrelated to system identifiers.

## Dependencies
- Canonical source agreement with `README.md` and `docs/architecture/system_registry.md`.

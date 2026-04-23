# Plan — SYS-REDUCE-01 — 2026-04-23

## Prompt type
PLAN

## Roadmap item
SYS-REDUCE-01

## Objective
Reduce and harden the canonical 3-letter system registry so active authorities match executable ownership, and add deterministic validation against future taxonomy sprawl.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/architecture/system_registry.md | MODIFY | Rewrite canonical registry into active/merged/future/artifact sections with explicit authority metadata and statuses. |
| docs/architecture/system_inventory_audit.md | CREATE | Record evidence-grounded inventory of discovered 3-letter systems and keep/merge/demote/remove actions. |
| docs/architecture/system_registry_reduction_decision.md | CREATE | Capture reduction rationale, boundary decisions, and control-loop hardening outcomes. |
| scripts/validate_system_registry.py | CREATE | Add deterministic registry guardrail and registry-to-code drift validation. |
| tests/test_system_registry_validation.py | CREATE | Add test coverage for duplicate, metadata, path existence, placeholder contradiction, and runtime drift checks. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_system_registry_validation.py`
2. `python scripts/validate_system_registry.py`

## Scope exclusions
- Do not refactor runtime implementations unrelated to registry ownership declarations.
- Do not change schema contracts under `contracts/schemas/`.
- Do not modify roadmap sequencing artifacts.

## Dependencies
- Canonical references: `README.md` and `docs/architecture/system_registry.md`.

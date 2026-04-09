# Plan — BATCH-SYS-ENF-01 — 2026-04-09

## Prompt type
PLAN

## Roadmap item
BATCH-SYS-ENF-01

## Objective
Harden system-registry ownership boundaries and add fail-closed, machine-checkable drift enforcement for high-risk authority leaks.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/architecture/system_registry.md | MODIFY | Tighten ownership language and remove authority overlap across targeted systems. |
| scripts/validate_system_registry_boundaries.py | CREATE | Add strict registry-boundary validator for ownership conflicts and forbidden authority drift. |
| tests/test_system_registry_boundary_enforcement.py | CREATE | Add deterministic tests for parser output, ownership uniqueness checks, forbidden patterns, and fail-closed admission path assumptions. |
| docs/reviews/system_registry_boundary_hardening_review.md | CREATE | Record what changed, tightened overlaps, remaining ambiguities/gaps, and architecture judgment limits. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_system_registry_boundary_enforcement.py`
2. `python scripts/validate_system_registry_boundaries.py`
3. `pytest tests/test_contracts.py`

## Scope exclusions
- Do not redesign the architecture or introduce speculative new systems.
- Do not modify unrelated governance or runtime modules.
- Do not weaken registry language merely to satisfy checks.

## Dependencies
- docs/architecture/system_registry.md must remain canonical for role ownership.
- docs/governance/strategy_control_doc.md constraints must remain intact.

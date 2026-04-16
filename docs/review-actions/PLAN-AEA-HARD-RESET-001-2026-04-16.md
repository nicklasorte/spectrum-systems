# Plan — AEA-HARD-RESET-001 — 2026-04-16

## Prompt type
PLAN

## Roadmap item
AEA-HARD-RESET-001

## Objective
Surgically remove the violating AEA layer and associated cross-owner artifact contracts so registry guard passes fail-closed.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-AEA-HARD-RESET-001-2026-04-16.md | CREATE | Plan-first hard reset trace. |
| spectrum_systems/modules/runtime/aea_ai_enforcement_autonomy.py | DELETE | Remove centralized AEA runtime layer. |
| tests/test_aea_ai_enforcement_autonomy.py | DELETE | Remove centralized AEA layer tests. |
| contracts/schemas/*AEA reset list* | DELETE | Remove overlapping AEA schema surfaces. |
| contracts/examples/*AEA reset list* | DELETE | Remove matching overlapping examples. |
| contracts/standards-manifest.json | MODIFY | Remove references to deleted AEA artifacts. |

## Scope exclusions
- No broad refactor.
- No new cross-owner orchestration layer.
- No reintroduction of deleted AEA surfaces in this repair.

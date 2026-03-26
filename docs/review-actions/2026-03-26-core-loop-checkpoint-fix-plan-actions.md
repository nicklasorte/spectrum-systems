# Core-Loop Checkpoint Fix Plan — Action Tracker

- **Source Review:** `docs/reviews/2026-03-26-core-loop-checkpoint-fix-plan.md`
- **Owner:** Codex
- **Last Updated:** 2026-03-26

## Critical Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Publish the canonical checkpoint review artifact pair (`docs/reviews/2026-03-26-core-loop-checkpoint-review.json` and `.md`) so contract validation and finding ingestion can run against authoritative input. | Review owner | Open | Upstream checkpoint artifact production | Required to replace fallback-based planning with authoritative JSON-driven planning. |

## High-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | Re-run fix-plan generation using authoritative JSON artifact as source of truth once CR-1 is complete. | Codex | Open | CR-1 | Must preserve trust-boundary ranking and minimal safe bundling rules from the current plan. |

## Medium-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | Confirm whether deferred watch items remain non-blocking after authoritative artifact ingestion. | Review owner | Open | HI-1 | If status changes, promote to blocking bundle and issue implementation prompt. |

## Low-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| LI-1 | Keep `jsonschema.RefResolver` deprecation warnings tracked as maintenance debt outside trust-boundary closure path. | Runtime maintainers | Open | None | Explicitly non-blocking for this checkpoint closure unless warning scope expands into trust surfaces. |

## Blocking Items
- CR-1 blocks authoritative completion of the original request because requested input artifacts are currently absent.

## Deferred Items
- Legacy replay adapter compatibility-surface monitoring remains deferred watch-only unless future changes re-open trust-boundary ambiguity.

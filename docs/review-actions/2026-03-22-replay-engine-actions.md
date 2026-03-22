# Architecture Review Action Tracker — Replay Engine Review

- **Source Review:** `docs/reviews/2026-03-22-replay-engine-review.md`
- **Owner:** TBD
- **Last Updated:** 2026-03-22

## Critical Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Update `replay_result.schema.json` to include optional `drift_result` property, or restructure `run_replay` return as envelope to avoid post-validation mutation | TBD | Open | None | Returned artifact currently violates `additionalProperties: false` |

## High-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | Replace `except Exception` fallback in `run_replay` (line 950) with raised `ReplayEngineError` to enforce fail-closed behavior | TBD | Open | None | Current handler silently absorbs canonical-path failures |

## Medium-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | Add test for indeterminate/exception path in `run_replay` (monkeypatch `run_control_loop` to raise) | TBD | Open | HI-1 (test assertions depend on fix direction) | Most failure-prone path has zero coverage |

## Low-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| LI-1 | Add parametrized type-guard tests for `run_replay` inputs (`None`, string, int) | TBD | Open | None | Straightforward guards, low regression risk |

## Blocking Items
- CR-1 blocks any downstream workflow that re-validates replay result artifacts (audit ingestion, drift pipelines).

## Deferred Items
- Review of BP legacy replay paths (`execute_replay`, `replay_run`) — trigger: when legacy paths are scheduled for deprecation.

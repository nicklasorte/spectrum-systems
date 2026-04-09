# Plan — BATCH-SYS-ENF-04B — 2026-04-09

## Prompt type
BUILD

## Roadmap item
[BATCH-SYS-ENF-04B] Repair top-level conductor happy paths after evidence-gate hardening

## Objective
Repair TLC happy-path evidence assembly so valid conductor-driven flows provide governed evidence required by ENF-04 gates, while incomplete paths remain fail-closed.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-SYS-ENF-04B-2026-04-09.md | CREATE | Plan-first artifact for multi-file conductor seam repair. |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY (expected) | Ensure conductor assembles and forwards required governed evidence for valid happy paths. |
| spectrum_systems/modules/runtime/closure_decision_engine.py | MODIFY (if needed) | Keep gate semantics intact while fixing conductor input seam mismatches only. |
| tests/test_top_level_conductor.py | MODIFY | Update/repair happy-path fixtures and assertions to explicitly provide valid governed evidence. |
| docs/reviews/top_level_conductor_evidence_assembly_repair_review.md | CREATE | Document root cause, repaired seam, and preserved fail-closed invariants. |

## Validation steps
1. `pytest tests/test_top_level_conductor.py -k "golden_integration_run_ready_for_merge or sel_enforced_at_required_boundaries or run_from_roadmap_executes_bounded_steps"`
2. `pytest tests/test_top_level_conductor.py`
3. `pytest tests/test_closure_decision_engine.py tests/test_sequence_transition_policy.py tests/test_github_closure_continuation.py`

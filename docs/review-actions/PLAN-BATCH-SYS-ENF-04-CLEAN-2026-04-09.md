# Plan — BATCH-SYS-ENF-04-CLEAN — 2026-04-09

## Prompt type
BUILD

## Roadmap item
BATCH-SYS-ENF-04-CLEAN

## Objective
Ensure promotion-capable CDE outcomes are only possible when governed evidence is complete, while preserving non-promotion completion flows and fail-closed behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/closure_decision_engine.py | MODIFY | Add explicit promotion evidence completeness gate and fail-closed blocking reasons in CDE. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Harden promotion consumer checks so closure artifact existence is not treated as promotion authorization. |
| spectrum_systems/modules/review_promotion_gate.py | MODIFY | Prevent downstream gate from treating any closure artifact as promotion-safe without promotability/evidence completeness. |
| tests/test_closure_decision_engine.py | MODIFY | Add focused fail-closed coverage for missing eval summary, required eval completeness, indeterminate/failing evals, traceability, certification, and non-promotion paths. |
| tests/test_sequence_transition_policy.py | MODIFY | Add promotion consumer tests proving non-promotable CDE outputs are rejected. |
| tests/test_review_promotion_gate.py | MODIFY | Add coverage that review promotion gate requires promotable/evidence-complete CDE output before clean status. |
| docs/reviews/cde_evidence_completeness_hardening_review.md | CREATE | Record evidence requirements, fail-open closures, compatibility choices, and remaining gaps. |

## Contracts touched
None planned; use existing closure_decision_artifact schema fields where possible for compatibility safety.

## Tests that must pass after execution
1. `pytest tests/test_closure_decision_engine.py`
2. `pytest tests/test_sequence_transition_policy.py`
3. `pytest tests/test_review_promotion_gate.py`
4. `pytest tests/test_top_level_conductor.py`

## Scope exclusions
- Do not transfer promotion authority from CDE to TLC, RDX, SEL, or review modules.
- Do not broaden certification semantics beyond already-modeled promotion paths.
- Do not perform unrelated refactors in orchestration/runtime modules.

## Dependencies
- None.

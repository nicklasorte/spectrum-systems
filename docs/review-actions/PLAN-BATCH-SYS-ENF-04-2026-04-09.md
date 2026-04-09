# Plan — BATCH-SYS-ENF-04 — 2026-04-09

## Prompt type
BUILD

## Roadmap item
[BATCH-SYS-ENF-04] CDE Evidence Completeness + Certification Gate

## Objective
Harden CDE and promotion consumers so promotable closure outcomes are impossible unless governed evidence is complete (eval, trace, certification, and existing replay/consistency gates), with explicit fail-closed reasons for missing or indeterminate evidence.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-SYS-ENF-04-2026-04-09.md | CREATE | Required plan-first artifact for this multi-file fail-closed hardening batch. |
| spectrum_systems/modules/runtime/closure_decision_engine.py | MODIFY | Enforce CDE evidence completeness gates for promotable outcomes (eval, trace, certification, indeterminate handling). |
| spectrum_systems/modules/runtime/github_closure_continuation.py | MODIFY | Require promotion gate evidence completeness from CDE artifact instead of artifact-exists heuristics. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Require promotable CDE decision/evidence completeness on canonical promotion transition. |
| tests/test_closure_decision_engine.py | MODIFY | Add fail-closed tests for missing eval summary/results, indeterminate eval, trace continuity, certification evidence. |
| tests/test_promotion_gate_decision.py | MODIFY | Verify downstream promotion artifact blocks when CDE decision is non-promotable or evidence-incomplete. |
| tests/test_sequence_transition_policy.py | MODIFY | Verify promoted transition rejects non-lock or evidence-incomplete CDE artifacts. |
| docs/reviews/cde_evidence_completeness_gate_review.md | CREATE | Required review note documenting closed fail-open paths and remaining certification rigor gaps. |

## Scope
- No architecture redesign and no new decision authority outside CDE.
- Preserve fail-closed semantics; strengthen promotion/canonical-state gates only.
- Reuse existing certification/replay/trust-spine seams where already modeled.

## Validation steps
1. `pytest tests/test_closure_decision_engine.py tests/test_promotion_gate_decision.py tests/test_sequence_transition_policy.py`
2. `pytest tests/test_contracts.py`
3. `pytest tests/test_module_architecture.py`

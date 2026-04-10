# Plan — BATCH-GOV-B-FIX-01 — 2026-04-10

## Prompt type
PLAN

## Roadmap item
BATCH-GOV-B-FIX-01 — Enforce true CDE authority (remove upstream decision leakage)

## Objective
Apply a surgical authority correction so CDE remains the sole decision authority for closure, promotion readiness, and bounded next-step classification; remove TLC synthetic closure inputs, remove RQX closure semantics, enforce SEL artifact-only closure gating, and normalize closure state blocking behavior.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY | Remove synthetic closure payloads, require real review artifacts, and prevent TLC reinterpretation of CDE decisions. |
| spectrum_systems/modules/runtime/system_enforcement_layer.py | MODIFY | Enforce closure authority from real CDE artifact only and strict OPEN/LOCKED/CLOSED execution blocking semantics. |
| spectrum_systems/modules/review_queue_executor.py | MODIFY | Remove authoritative merge-ready booleans and emit non-authoritative readiness signals only. |
| spectrum_systems/modules/review_promotion_gate.py | MODIFY | Stop consuming authoritative booleans from RQX readiness artifact and preserve CDE-only authority checks. |
| contracts/schemas/review_merge_readiness_artifact.schema.json | MODIFY | Strip closure-authority fields; schema text explicitly marks output as CDE input signal only. |
| contracts/examples/review_merge_readiness_artifact.json | MODIFY | Align example with non-authoritative signal contract. |
| contracts/standards-manifest.json | MODIFY | Version bump + notes for updated review_merge_readiness_artifact contract. |
| tests/test_top_level_conductor.py | MODIFY | Add TLC boundary tests for no synthetic closure inputs and no CDE output rewriting. |
| tests/test_system_enforcement_layer.py | MODIFY | Add SEL tests for strict closure artifact/state enforcement. |
| tests/test_review_queue_executor.py | MODIFY | Assert RQX readiness output is non-authoritative. |
| tests/test_review_promotion_gate.py | MODIFY | Update promotion gate expectations to non-authoritative readiness signal shape. |
| docs/reviews/gov_b_authority_redteam_post_fix.md | CREATE | Targeted adversarial validation report for GOV-B post-fix seam. |

## Contracts touched
- `review_merge_readiness_artifact` (schema + example + manifest entry)

## Tests that must pass after execution
1. `pytest tests/test_top_level_conductor.py`
2. `pytest tests/test_system_enforcement_layer.py`
3. `pytest tests/test_review_queue_executor.py`
4. `pytest tests/test_review_promotion_gate.py`
5. `pytest tests/test_contracts.py`

## Scope exclusions
- No new systems.
- No architecture redesign.
- No duplicated authority logic outside CDE.
- No refactors unrelated to GOV-B authority seam.

# Plan — RUNTIME-PROVENANCE-ANCHORS — 2026-03-29

## Prompt type
PLAN

## Roadmap item
Post-runtime-identity hardening slice (provenance anchors across persistence and downstream seams)

## Objective
Enforce deterministic fail-closed run_id/trace_id provenance verification at write/reload and replay→eval / eval→certification seams, with explicit policy for allowed cross-run references.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RUNTIME-PROVENANCE-ANCHORS-2026-03-29.md | CREATE | Required scoped plan artifact before multi-file hardening |
| PLANS.md | MODIFY | Register this plan in active plans table |
| spectrum_systems/modules/runtime/provenance_verification.py | CREATE | Governed provenance verification module for required IDs and continuity checks |
| spectrum_systems/modules/runtime/trace_store.py | MODIFY | Wire identity verification into disk persistence/reload seam |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Enforce replay→eval identity continuity and fail-closed errors |
| spectrum_systems/modules/governance/done_certification.py | MODIFY | Enforce eval/control/certification reference identity consistency with explicit cross-run allowance |
| contracts/docs/provenance_identity_continuity.md | CREATE | Contract doc for trace/run continuity and allowed cross-run/cross-trace references |
| tests/test_provenance_verification.py | CREATE | Focused regression tests for verifier behavior and non-mutation |
| tests/test_trace_store.py | MODIFY | Regression coverage for persisted artifact identity reload checks |
| tests/test_replay_engine.py | MODIFY | Regression coverage for replay→eval trace/run mismatch rejection |
| tests/test_done_certification.py | MODIFY | Regression coverage for run mismatch rejection and explicit cross-run allowance |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_provenance_verification.py tests/test_trace_store.py tests/test_replay_engine.py tests/test_done_certification.py`
2. `pytest tests/test_contracts.py`
3. `pytest`

## Scope exclusions
- Do not modify JSON Schema contracts or standards-manifest versions.
- Do not redesign runtime control architecture beyond seam hardening.
- Do not refactor unrelated modules.

## Dependencies
- Runtime identity enforcement baseline (`identity_enforcement.py`) remains authoritative for required field semantics.

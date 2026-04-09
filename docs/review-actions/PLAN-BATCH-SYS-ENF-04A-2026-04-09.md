# Plan — BATCH-SYS-ENF-04A — 2026-04-09

## Prompt type
BUILD

## Roadmap item
[BATCH-SYS-ENF-04A] Repair contract preflight block after CDE evidence completeness hardening

## Objective
Repair contract preflight strategy gate failures introduced after ENF-04 without weakening the CDE evidence-completeness fail-closed promotion guard.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-SYS-ENF-04A-2026-04-09.md | CREATE | Required plan-first artifact for multi-file contract compatibility repair. |
| outputs/contract_preflight/contract_preflight_report.md | CREATE/MODIFY | Inspect and retain evidence of the blocking preflight findings. |
| outputs/contract_preflight/contract_preflight_report.json | CREATE/MODIFY | Inspect and retain machine-readable preflight findings. |
| outputs/contract_preflight/contract_preflight_result_artifact.json | CREATE/MODIFY | Inspect governed artifact result and strategy gate status. |
| contracts/schemas/closure_decision_artifact.schema.json | MODIFY (if needed) | Apply compatibility-safe schema versioning/field evolution for ENF-04 semantics. |
| contracts/examples/closure_decision_artifact.json | MODIFY (if needed) | Keep examples aligned with schema + runtime behavior. |
| contracts/standards-manifest.json | MODIFY (if needed) | Register any contract version update required by compatibility fix. |
| spectrum_systems/modules/runtime/closure_decision_engine.py | MODIFY (if needed) | Keep producer output contract-compliant while preserving evidence gate. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY (if needed) | Keep consumer compatible with versioned/bridged contract semantics. |
| tests/test_contract_preflight.py | MODIFY (if needed) | Assert preflight passes with repaired contract semantics. |
| tests/test_contracts.py | MODIFY (if needed) | Validate contract and examples consistency after repair. |
| docs/reviews/cde_evidence_completeness_contract_repair_review.md | CREATE | Document root cause, compatibility repair, and preservation of ENF-04 gate. |

## Validation steps
1. `python scripts/run_contract_preflight.py`
2. `pytest tests/test_contract_preflight.py tests/test_contracts.py`
3. `pytest tests/test_closure_decision_engine.py tests/test_promotion_gate_decision.py tests/test_sequence_transition_policy.py`

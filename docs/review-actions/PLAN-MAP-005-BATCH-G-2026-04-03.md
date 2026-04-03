# Plan — MAP-005 — 2026-04-03

## Prompt type
PLAN

## Roadmap item
MAP-005 — BATCH-G: Certification + Promotion Enforcement

## Objective
Ensure done certification and promotion gating are system-readiness authoritative by requiring governed review/eval/control signals and deterministic fail-closed readiness outcomes.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-MAP-005-BATCH-G-2026-04-03.md | CREATE | Required plan-first artifact for multi-file governance changes |
| spectrum_systems/modules/governance/done_certification.py | MODIFY | Add system-readiness signal consumption and PASS/WARN/FREEZE/FAIL classification |
| spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py | MODIFY | Enforce promotion gate against readiness-aware certification outcomes |
| contracts/schemas/done_certification_record.schema.json | MODIFY | Expand certification status vocabulary and require system-level readiness checks |
| contracts/examples/done_certification_record.json | MODIFY | Keep golden-path example aligned with updated certification schema |
| tests/test_done_certification.py | MODIFY | Add positive/negative/determinism coverage for readiness-aware certification behavior |
| tests/test_evaluation_enforcement_bridge.py | MODIFY | Assert promotion enforcement behavior for warn/freeze/block certification outputs |
| tests/test_repo_health_eval.py | MODIFY | Add explicit integration assertions for readiness thresholds used by certification |
| contracts/standards-manifest.json | MODIFY | Version bump and contract version update for done_certification_record schema changes |

## Contracts touched
- done_certification_record (schema and example)
- standards-manifest version and done_certification_record entry

## Tests that must pass after execution
1. `pytest tests/test_done_certification.py`
2. `pytest tests/test_evaluation_enforcement_bridge.py`
3. `pytest tests/test_repo_health_eval.py`
4. `pytest tests/test_control_loop_certification.py`
5. `pytest tests/test_pqx_sequence_runner.py`
6. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
7. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not introduce a parallel certification pipeline.
- Do not redesign PQX execution semantics.
- Do not modify unrelated governance modules or non-impacted contracts.
- Do not weaken fail-closed behavior for missing/invalid signals.

## Dependencies
- Existing DONE-01 and promotion enforcement seams remain the sole authority path.
- Existing repo_review_snapshot and repo_health_eval contracts remain authoritative inputs.

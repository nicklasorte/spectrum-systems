# Plan — RAX-ROADMAP-SERIAL-01 — 2026-04-12

## Prompt type
PLAN

## Roadmap item
RAX-ROADMAP-SERIAL-01

## Objective
Implement RAX-03 through RAX-12 as deterministic, fail-closed, artifact-first runtime and contract updates covering discovery, conflict arbitration, non-authority fencing, drift observability, governed eval admission, policy regression, judgment compilation, replay expansion, artifact intelligence, and promotion hard-gating.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RAX-ROADMAP-SERIAL-01-2026-04-12.md | CREATE | Required multi-file BUILD plan declaration |
| spectrum_systems/modules/runtime/rax_eval_runner.py | MODIFY | Add serial roadmap logic and deterministic artifact generation/gating |
| contracts/schemas/rax_eval_case_set.schema.json | MODIFY | Extend governed eval case structure for mutation/combinatorial discovery classes |
| contracts/examples/rax_eval_case_set.json | MODIFY | Add RAX-03 discovery fixtures and combinatorial cases |
| contracts/schemas/rax_conflict_arbitration_record.schema.json | CREATE | Contract for deterministic cross-eval conflict arbitration artifact |
| contracts/examples/rax_conflict_arbitration_record.json | CREATE | Golden example for conflict arbitration artifact |
| contracts/schemas/rax_judgment_record.schema.json | CREATE | Contract for non-authoritative RAX judgment compilation artifact |
| contracts/examples/rax_judgment_record.json | CREATE | Golden example for judgment artifact |
| contracts/schemas/rax_trend_report.schema.json | CREATE | Contract for longitudinal trend report artifact |
| contracts/examples/rax_trend_report.json | CREATE | Golden example for trend report |
| contracts/schemas/rax_trust_posture_snapshot.schema.json | CREATE | Contract for trust posture snapshot |
| contracts/examples/rax_trust_posture_snapshot.json | CREATE | Golden example for trust posture snapshot |
| contracts/schemas/rax_improvement_recommendation_record.schema.json | CREATE | Contract for derived recommendation artifact |
| contracts/examples/rax_improvement_recommendation_record.json | CREATE | Golden example for recommendation record |
| contracts/schemas/rax_promotion_hard_gate_record.schema.json | CREATE | Contract for promotion evidence hard-gate result |
| contracts/examples/rax_promotion_hard_gate_record.json | CREATE | Golden example for promotion hard-gate artifact |
| contracts/standards-manifest.json | MODIFY | Register new/updated RAX contracts and versions |
| tests/test_rax_eval_runner.py | MODIFY | Add RAX-03..RAX-12 unit coverage |
| tests/test_roadmap_expansion_contracts.py | MODIFY | Validate new RAX contract examples and schema guards |

## Contracts touched
rax_eval_case_set, rax_conflict_arbitration_record, rax_judgment_record, rax_trend_report, rax_trust_posture_snapshot, rax_improvement_recommendation_record, rax_promotion_hard_gate_record, standards-manifest entries.

## Tests that must pass after execution

1. `pytest tests/test_rax_eval_runner.py tests/test_rax_redteam_adversarial_pack.py tests/test_rax_interface_assurance.py`
2. `pytest tests/test_roadmap_expansion_contracts.py tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`

## Scope exclusions

- Do not modify non-RAX runtime subsystems.
- Do not alter canonical ownership in `docs/architecture/system_registry.md`.
- Do not introduce authority-bearing control decisions from RAX artifacts.

## Dependencies

- RAX-RED-01 complete.
- RAX-RED-02 complete.

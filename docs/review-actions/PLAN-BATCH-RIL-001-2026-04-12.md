# Plan — BATCH-RIL-001 — 2026-04-12

## Prompt type
PLAN

## Roadmap item
BATCH-RIL-001 (FRE-16, RIL-01..RIL-08F)

## Objective
Implement a repo-native FRE closeout gate and a deterministic fail-closed RIL interpretation foundation with bounded contracts, replay validation, ambiguity/contradiction handling, control-signal hardening, coverage/drift telemetry, and FRE↔RIL alignment checks.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-RIL-001-2026-04-12.md | CREATE | Required plan-first artifact for multi-file BUILD scope. |
| PLANS.md | MODIFY | Register active plan in canonical plan index. |
| contracts/schemas/fre_closeout_gate_record.schema.json | CREATE | FRE-16 closeout gate contract. |
| contracts/schemas/failure_packet.schema.json | CREATE | RIL-01 normalized failure intake boundary contract. |
| contracts/schemas/interpretation_record.schema.json | CREATE | RIL interpretation output boundary contract. |
| contracts/schemas/interpretation_eval_result.schema.json | CREATE | RIL eval harness output contract. |
| contracts/schemas/interpretation_readiness_record.schema.json | CREATE | Candidate-only readiness contract. |
| contracts/schemas/interpretation_conflict_record.schema.json | CREATE | Cross-source contradiction contract. |
| contracts/schemas/interpretation_bundle.schema.json | CREATE | RIL bundle contract joining interpretation outputs. |
| contracts/schemas/interpretation_replay_validation_record.schema.json | CREATE | RIL-08A deterministic replay result contract. |
| contracts/schemas/interpretation_ambiguity_signal.schema.json | CREATE | RIL-08B ambiguity budget signal contract. |
| contracts/schemas/interpretation_control_signal_validation.schema.json | CREATE | RIL-08C shadow-authority validation contract. |
| contracts/schemas/interpretation_repair_alignment_record.schema.json | CREATE | RIL-08F FRE alignment contract. |
| contracts/schemas/interpretation_effectiveness_record.schema.json | CREATE | RIL-07 effectiveness tracking contract. |
| contracts/schemas/interpretation_coverage_report.schema.json | CREATE | RIL-08D required class coverage contract. |
| contracts/schemas/failure_class_drift_record.schema.json | CREATE | RIL-08E taxonomy drift detection contract. |
| contracts/examples/fre_closeout_gate_record.json | CREATE | Golden example for FRE-16 closeout gate. |
| contracts/examples/failure_packet.json | CREATE | Golden example for normalized RIL failure packet. |
| contracts/examples/interpretation_record.json | CREATE | Golden example for interpretation record. |
| contracts/examples/interpretation_eval_result.json | CREATE | Golden example for eval result. |
| contracts/examples/interpretation_readiness_record.json | CREATE | Golden example for readiness record. |
| contracts/examples/interpretation_conflict_record.json | CREATE | Golden example for contradiction record. |
| contracts/examples/interpretation_bundle.json | CREATE | Golden example for interpretation bundle. |
| contracts/examples/interpretation_replay_validation_record.json | CREATE | Golden example for replay validation. |
| contracts/examples/interpretation_ambiguity_signal.json | CREATE | Golden example for ambiguity budget signaling. |
| contracts/examples/interpretation_control_signal_validation.json | CREATE | Golden example for control-signal validation. |
| contracts/examples/interpretation_repair_alignment_record.json | CREATE | Golden example for interpretation-repair consistency. |
| contracts/examples/interpretation_effectiveness_record.json | CREATE | Golden example for effectiveness tracking. |
| contracts/examples/interpretation_coverage_report.json | CREATE | Golden example for coverage enforcement. |
| contracts/examples/failure_class_drift_record.json | CREATE | Golden example for drift monitor output. |
| contracts/standards-manifest.json | MODIFY | Register all new contracts and versions. |
| spectrum_systems/modules/runtime/fre_repair_flow.py | MODIFY | Add FRE-16 closeout gate constructor and validations. |
| spectrum_systems/modules/runtime/ril_interpretation.py | CREATE | Implement RIL normalization/eval/readiness/replay/ambiguity/control/alignment/effectiveness/coverage/drift logic. |
| tests/test_fre_repair_flow.py | MODIFY | Add FRE-16 closeout gate operational tests. |
| tests/test_ril_interpretation.py | CREATE | Add deterministic fail-closed tests covering RIL-01..RIL-08F behavior. |
| tests/test_contract_enforcement.py | MODIFY | Register new manifest contract expectations. |

## Contracts touched
- Add `fre_closeout_gate_record` (1.0.0).
- Add `failure_packet` (1.0.0).
- Add `interpretation_record` (1.0.0).
- Add `interpretation_eval_result` (1.0.0).
- Add `interpretation_readiness_record` (1.0.0).
- Add `interpretation_conflict_record` (1.0.0).
- Add `interpretation_bundle` (1.0.0).
- Add `interpretation_replay_validation_record` (1.0.0).
- Add `interpretation_ambiguity_signal` (1.0.0).
- Add `interpretation_control_signal_validation` (1.0.0).
- Add `interpretation_repair_alignment_record` (1.0.0).
- Add `interpretation_effectiveness_record` (1.0.0).
- Add `interpretation_coverage_report` (1.0.0).
- Add `failure_class_drift_record` (1.0.0).
- Update `contracts/standards-manifest.json` registry entries.

## Tests that must pass after execution
1. `pytest tests/test_fre_repair_flow.py tests/test_ril_interpretation.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`

## Scope exclusions
- Do not add execution authority to RIL or FRE surfaces.
- Do not add direct repair execution in RIL.
- Do not refactor unrelated runtime modules or roadmap families.

## Dependencies
- Existing FRE bounded artifact contracts and runtime flow remain authoritative upstream for RIL alignment checks.

# Plan — RAX-FRE-SERIAL-01 — 2026-04-12

## Prompt type
PLAN

## Roadmap item
RAX-FRE-SERIAL-01

## Objective
Implement operational RAX closeout wiring (CI/promotion hard-gate enforcement, external artifact emission, and audit stabilization) plus FRE bounded repair foundation contracts, fencing, generation, evaluation, and readiness artifacts with fail-closed tests.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RAX-FRE-SERIAL-01-2026-04-12.md | CREATE | Required written plan prior to multi-file BUILD work. |
| contracts/schemas/rax_operational_gate_record.schema.json | CREATE | Contract-first schema for operational RAX gate artifact emitted and consumed in promotion path. |
| contracts/examples/rax_operational_gate_record.json | CREATE | Canonical example for operational RAX gate artifact. |
| contracts/schemas/repair_candidate.schema.json | CREATE | FRE boundary contract for bounded non-authoritative repair candidate artifacts. |
| contracts/schemas/repair_eval_result.schema.json | CREATE | FRE boundary contract for evaluation output over repair candidates. |
| contracts/schemas/repair_effectiveness_record.schema.json | CREATE | FRE contract for post-eval effectiveness tracking without authority. |
| contracts/schemas/repair_recurrence_record.schema.json | CREATE | FRE contract for recurrence tracking linked to repair candidate lineage. |
| contracts/schemas/repair_bundle.schema.json | CREATE | FRE aggregate contract for candidate/eval/evidence/readiness references. |
| contracts/schemas/repair_readiness_candidate.schema.json | CREATE | Candidate-only readiness contract explicitly fenced from authority. |
| contracts/examples/repair_candidate.json | CREATE | Example payload for repair_candidate contract. |
| contracts/examples/repair_eval_result.json | CREATE | Example payload for repair_eval_result contract. |
| contracts/examples/repair_effectiveness_record.json | CREATE | Example payload for repair_effectiveness_record contract. |
| contracts/examples/repair_recurrence_record.json | CREATE | Example payload for repair_recurrence_record contract. |
| contracts/examples/repair_bundle.json | CREATE | Example payload for repair_bundle contract. |
| contracts/examples/repair_readiness_candidate.json | CREATE | Example payload for candidate-only repair readiness contract. |
| contracts/standards-manifest.json | MODIFY | Register/version new and updated contracts. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Wire RAX operational gate as required promotion evidence in real transition path. |
| scripts/run_rax_operational_gate.py | MODIFY | Emit RAX trend/posture/recommendation/judgment artifacts through real CLI output flow. |
| .codex/skills/contract-boundary-audit/run.sh | MODIFY | Stabilize contract-boundary audit output and semantics for deterministic bounded reporting. |
| spectrum_systems/modules/runtime/fre_repair_flow.py | CREATE | FRE module for bounded candidate generation, eval harness, and readiness candidate assembly. |
| tests/test_sequence_transition_policy.py | MODIFY | Add fail-closed promotion tests for RAX operational gate enforcement. |
| tests/test_run_rax_operational_gate_cli.py | MODIFY | Verify external RAX artifact emission in CLI operational path. |
| tests/test_fre_repair_flow.py | CREATE | Unit coverage for FRE contracts, upstream/downstream fencing, determinism, eval harness, and readiness semantics. |
| tests/test_contract_boundary_audit.py | CREATE | Validate stabilized contract-boundary audit pass/warn/fail semantics and bounded output behavior. |
| tests/test_contract_enforcement.py | MODIFY | Add standards-manifest checks for new FRE and RAX operational contracts. |

## Contracts touched
- New: `rax_operational_gate_record` (`1.0.0`)
- New: `repair_candidate` (`1.0.0`)
- New: `repair_eval_result` (`1.0.0`)
- New: `repair_effectiveness_record` (`1.0.0`)
- New: `repair_recurrence_record` (`1.0.0`)
- New: `repair_bundle` (`1.0.0`)
- New: `repair_readiness_candidate` (`1.0.0`)
- Manifest updates in `contracts/standards-manifest.json`

## Tests that must pass after execution
1. `pytest tests/test_run_rax_operational_gate_cli.py tests/test_sequence_transition_policy.py tests/test_rax_eval_runner.py -q`
2. `pytest tests/test_fre_repair_flow.py tests/test_governed_repair_foundation.py tests/test_governed_repair_loop_execution.py -q`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py tests/test_contract_boundary_audit.py -q`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/contract-boundary-audit/run.sh`

## Scope exclusions
- Do not weaken trust-spine, closure decision, or existing promotion authority gates.
- Do not add repair execution authority to FRE artifacts or modules.
- Do not refactor unrelated runtime modules outside RAX/FRE and audit seams.
- Do not modify external repository manifests or ecosystem registry semantics.

## Dependencies
- Existing RAX primitives and `sequence_transition_policy` promotion path.
- Existing governed repair foundation packet/candidate flow and deterministic ID utilities.

# System Registry (Canonical Index)

## Core rules

1. **Single-responsibility ownership**: each governed responsibility has exactly one canonical owner.
2. **No-duplication rule**: no system may implement, enforce, or shadow a responsibility owned by another system.
3. **Artifact-first execution**: required transitions must be represented as governed artifacts.
4. **Fail-closed behavior**: missing required evidence blocks progression.
5. **Promotion requires certification**: promotion is prohibited without required certification evidence.

These rules are hard boundaries for architecture, contracts, execution, and validation.

## Canonical architecture split

The registry is intentionally split to reduce semantic sprawl and keep authority boundaries explicit.

- `system_registry_core.md` — authoritative runtime spine systems plus support planes.
- `system_registry_support.md` — grouped subsystem/support families (non-peer to runtime spine authorities).
- `system_registry_reserved.md` — reserved/non-active acronyms and future seams.
- `runtime_spine.md` — hard runtime chain and BLOCK/FREEZE/ALLOW semantics.

## Runtime authority summary

Authoritative runtime spine:

**AEX → PQX → EVL → TPA → CDE → SEL**

Mandatory gate overlays:

- REP (replay)
- LIN (lineage)
- OBS (observability)

Support planes (not minimal spine authorities): TLC, FRE, RIL, PRG.

## System Definitions

Compatibility note: this section remains parser-facing for SRG/preflight tooling. Detailed human-facing definitions live in `docs/architecture/system_registry_core.md`.

### AEX
- **acronym:** `AEX`
- **full_name:** `Admission and Execution Exchange`
- **role:** Admission boundary for governed execution requests.
- **owns:**
  - execution_admission
  - request_normalization
  - admission_record_emission
- **consumes:**
  - execution_request_artifact
  - request_context_metadata
- **produces:**
  - admission_decision_artifact
  - normalized_execution_request
  - admission_rejection_record
- **must_not_do:**
  - execute bounded work
  - issue policy admissibility decisions
  - issue closure or promotion decisions
- **details:** `docs/architecture/system_registry_core.md`

### PQX
- **acronym:** `PQX`
- **full_name:** `Prompt Queue Execution`
- **role:** Bounded execution authority.
- **owns:**
  - bounded_execution
  - execution_state_transitions
  - execution_trace_emission
- **consumes:**
  - admitted_execution_request
  - scoped_execution_bundle
- **produces:**
  - execution_result_artifact
  - execution_trace_artifact
- **must_not_do:**
  - admit requests
  - issue policy admissibility decisions
  - issue closure or promotion decisions
- **details:** `docs/architecture/system_registry_core.md`

### EVL
- **acronym:** `EVL`
- **full_name:** `Evaluation Authority`
- **role:** Required evaluation authority and gate.
- **owns:**
  - required_eval_registry
  - required_eval_decision
  - eval_coverage_verification
- **consumes:**
  - execution_output_artifacts
  - eval_dataset_and_test_artifacts
- **produces:**
  - required_eval_result
  - eval_coverage_record
  - eval_indeterminate_record
- **must_not_do:**
  - bypass missing eval evidence
  - override policy admissibility authority
  - issue final promotion decisions
- **details:** `docs/architecture/system_registry_core.md`

### TPA
- **acronym:** `TPA`
- **full_name:** `Trust and Policy Admissibility`
- **role:** Policy admissibility authority.
- **owns:**
  - policy_admissibility_decision
  - trust_boundary_evaluation
  - policy_result_emission
- **consumes:**
  - admitted_request_artifacts
  - required_eval_results
  - policy_input_evidence
- **produces:**
  - policy_admissibility_result
  - policy_block_record
- **must_not_do:**
  - execute bounded work
  - issue closure or promotion decisions
  - suppress policy failures
- **details:** `docs/architecture/system_registry_core.md`

### CDE
- **acronym:** `CDE`
- **full_name:** `Closure Decision Engine`
- **role:** Final decision authority for closure and promotion-readiness.
- **owns:**
  - closure_decision
  - promotion_readiness_decision
  - final_decision_artifact_emission
- **consumes:**
  - required_runtime_evidence_bundle
  - policy_and_gate_results
- **produces:**
  - closure_decision_artifact
  - promotion_readiness_decision_artifact
- **must_not_do:**
  - execute bounded work
  - enforce runtime actions directly
  - bypass required evidence gates
- **details:** `docs/architecture/system_registry_core.md`

### SEL
- **acronym:** `SEL`
- **full_name:** `Safety Enforcement Layer`
- **role:** Runtime enforcement authority.
- **owns:**
  - block_action_enforcement
  - freeze_action_enforcement
  - allow_action_enforcement
- **consumes:**
  - closure_and_promotion_decisions
  - authoritative_gate_outcomes
- **produces:**
  - enforcement_action_artifact
  - runtime_progression_state
- **must_not_do:**
  - invent decision authority
  - override failed authoritative gates
  - bypass fail_closed controls
- **details:** `docs/architecture/system_registry_core.md`

### REP
- **acronym:** `REP`
- **full_name:** `Replay Integrity`
- **role:** Replay gate overlay.
- **owns:**
  - replay_requirement_evaluation
  - replay_match_decision
  - replay_mismatch_detection
- **consumes:**
  - execution_artifacts
  - replay_artifacts
- **produces:**
  - replay_gate_result
  - replay_mismatch_failure_record
- **must_not_do:**
  - waive mandatory replay checks
  - issue closure decisions
  - issue promotion decisions
- **details:** `docs/architecture/system_registry_core.md`

### LIN
- **acronym:** `LIN`
- **full_name:** `Lineage Integrity`
- **role:** Lineage completeness gate overlay.
- **owns:**
  - lineage_completeness_verification
  - provenance_link_validation
  - lineage_block_decision
- **consumes:**
  - artifact_lineage_records
  - provenance_link_artifacts
- **produces:**
  - lineage_gate_result
  - lineage_failure_record
- **must_not_do:**
  - permit progression with incomplete lineage
  - issue closure decisions
  - issue promotion decisions
- **details:** `docs/architecture/system_registry_core.md`

### OBS
- **acronym:** `OBS`
- **full_name:** `Observability Completeness`
- **role:** Observability completeness gate overlay.
- **owns:**
  - required_trace_completeness_verification
  - observability_contract_validation
  - observability_block_decision
- **consumes:**
  - runtime_trace_artifacts
  - observability_contract_artifacts
- **produces:**
  - observability_gate_result
  - observability_failure_record
- **must_not_do:**
  - permit progression with missing required traces
  - issue closure decisions
  - issue promotion decisions
- **details:** `docs/architecture/system_registry_core.md`

### TLC
- **acronym:** `TLC`
- **full_name:** `Top-Level Conductor`
- **role:** Orchestration and routing support plane.
- **owns:**
  - orchestration_routing
  - execution_ordering_plan
  - orchestration_record_emission
- **consumes:**
  - admitted_work_items
  - runtime_status_artifacts
- **produces:**
  - routing_plan_artifact
  - orchestration_state_record
- **must_not_do:**
  - override authoritative gate outcomes
  - issue final closure decisions
  - issue enforcement actions
- **details:** `docs/architecture/system_registry_core.md`

### FRE
- **acronym:** `FRE`
- **full_name:** `Failure and Repair Engine`
- **role:** Failure diagnosis and bounded repair planning support plane.
- **owns:**
  - failure_classification
  - bounded_repair_planning
  - repair_candidate_artifact_generation
- **consumes:**
  - failure_evidence_artifacts
  - eval_and_enforcement_failures
- **produces:**
  - diagnosis_artifact
  - bounded_repair_plan_artifact
- **must_not_do:**
  - grant promotion authority
  - bypass failed gates
  - execute unrestricted repairs
- **details:** `docs/architecture/system_registry_core.md`

### RIL
- **acronym:** `RIL`
- **full_name:** `Review Interpretation Layer`
- **role:** Review interpretation and integration support plane.
- **owns:**
  - review_interpretation
  - interpretation_normalization
  - review_integration_artifact_generation
- **consumes:**
  - review_output_artifacts
  - runtime_evidence_bundles
- **produces:**
  - normalized_interpretation_artifact
  - review_integration_record
- **must_not_do:**
  - issue final closure decisions
  - issue enforcement actions
  - bypass core gates
- **details:** `docs/architecture/system_registry_core.md`

### PRG
- **acronym:** `PRG`
- **full_name:** `Program Governance`
- **role:** Program-level governance support plane.
- **owns:**
  - program_sequencing_constraints
  - governance_threshold_tracking
  - governance_constraint_artifact_emission
- **consumes:**
  - roadmap_inputs
  - budget_and_drift_telemetry
- **produces:**
  - governance_constraint_artifact
  - threshold_state_record
- **must_not_do:**
  - bypass runtime spine authorities
  - issue final closure decisions
  - issue enforcement actions
- **details:** `docs/architecture/system_registry_core.md`

## System addition rule

A new canonical system may be added only if all of the following are proven:

1. One unique authority.
2. One clear blocking failure it prevents.
3. One enforced contract surface.
4. One tested fail-closed boundary.
5. Explicit proof it cannot be a subsystem group or artifact family.

If these are not met, the capability must remain in support families or reserved status.

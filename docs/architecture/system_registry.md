# System Registry (Canonical)

## Core rules
1. **Artifact-first execution:** every stage consumes and emits governed artifact records.
2. **Fail-closed behavior:** missing lineage, eval coverage, policy clarity, or control decisions blocks progression.
3. **Promotion requires certification:** promotion readiness and certification remain explicit authority decisions.

## Canonical loop

`AEX → PQX → EVL → TPA → CDE → SEL`

Overlay authorities required in the same loop:

`REP + LIN + OBS + SLO`

## Active executable systems

### AEX
- **Status:** active
- **Purpose:** bounded admission boundary for repo-mutating execution requests.
- **Failure Prevented:** unauthorized or malformed execution entering runtime.
- **Signal Improved:** admission acceptance/rejection integrity.
- **Canonical Artifacts Owned:** `build_admission_record`, `normalized_execution_request`, `admission_rejection_record`.
- **Upstream Dependencies:** prompt/task requests, PR/task registry records.
- **Downstream Dependencies:** PQX, CTX, PRM.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/agent_golden_path.py`
  - `spectrum_systems/modules/runtime/execution_contracts.py`

### PQX
- **Status:** active
- **Purpose:** bounded execution engine for authorized slices/bundles.
- **Failure Prevented:** unbounded or policy-bypassing execution.
- **Signal Improved:** deterministic execution trace and closure records.
- **Canonical Artifacts Owned:** `pqx_slice_execution_record`, `pqx_bundle_execution_record`, `pqx_execution_closure_record`.
- **Upstream Dependencies:** AEX, TLC route artifacts, TPA gates.
- **Downstream Dependencies:** EVL, REP, OBS.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/pqx_execution_authority.py`
  - `spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py`
  - `spectrum_systems/modules/runtime/pqx_slice_runner.py`

### EVL
- **Status:** active
- **Purpose:** required evaluation authority and eval-gate control.
- **Failure Prevented:** promotion or closure without required eval evidence.
- **Signal Improved:** eval coverage completeness and risk/comparison signal quality.
- **Canonical Artifacts Owned:** `required_eval_coverage`, `evaluation_control_decision`, `eval_slice_summary`, `risk_classification_artifact`, `comparison_run_artifact`.
- **Upstream Dependencies:** PQX outputs, dataset/registry declarations.
- **Downstream Dependencies:** TPA, CDE, GOV.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/eval_registry.py`
  - `spectrum_systems/modules/runtime/required_eval_coverage.py`
  - `spectrum_systems/modules/runtime/evaluation_control.py`
  - `spectrum_systems/modules/runtime/repo_health_eval.py`

### TPA
- **Status:** active
- **Purpose:** trust/policy adjudication authority for execution and promotion inputs.
- **Failure Prevented:** ambiguous policy interpretation and trust-boundary bypass.
- **Signal Improved:** trust posture and policy-compliance confidence.
- **Canonical Artifacts Owned:** `trust_policy_decision`, `policy_violation_record`, `trust_spine_invariant_result`.
- **Upstream Dependencies:** EVL, POL.
- **Downstream Dependencies:** CDE, SEL.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/tpa_complexity_governance.py`
  - `spectrum_systems/modules/runtime/trust_spine_invariants.py`
  - `spectrum_systems/modules/runtime/decision_gating.py`

### CDE
- **Status:** active
- **Purpose:** control/closure decision authority.
- **Failure Prevented:** implicit closure/promotion without explicit control decisions.
- **Signal Improved:** closure-readiness decision traceability.
- **Canonical Artifacts Owned:** `closure_decision_artifact`, `promotion_readiness_decision`, `readiness_to_close`.
- **Upstream Dependencies:** EVL, TPA, LIN, REP.
- **Downstream Dependencies:** SEL, GOV, PRA.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/closure_decision_engine.py`
  - `spectrum_systems/modules/runtime/cde_decision_flow.py`

### SEL
- **Status:** active
- **Purpose:** enforcement authority for fail-closed runtime actions.
- **Failure Prevented:** non-enforced control outcomes and unsafe progression.
- **Signal Improved:** enforcement execution integrity and block action coverage.
- **Canonical Artifacts Owned:** `enforcement_action_record`, `enforcement_block_record`, `control_surface_enforcement_result`.
- **Upstream Dependencies:** CDE and TPA decisions.
- **Downstream Dependencies:** runtime executors, OBS.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/sel_enforcement_foundation.py`
  - `spectrum_systems/modules/runtime/system_enforcement_layer.py`
  - `spectrum_systems/modules/runtime/enforcement_engine.py`

### REP
- **Status:** active
- **Purpose:** replay integrity authority for deterministic decision/execution replay.
- **Failure Prevented:** irreproducible decisions and unverifiable postmortems.
- **Signal Improved:** replay reproducibility and integrity confidence.
- **Canonical Artifacts Owned:** `replay_run_record`, `replay_decision_record`, `replay_integrity_result`.
- **Upstream Dependencies:** PQX, CDE, LIN.
- **Downstream Dependencies:** EVL, GOV, FRE.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/replay_engine.py`
  - `spectrum_systems/modules/runtime/replay_decision_engine.py`
  - `spectrum_systems/modules/runtime/replay_governance.py`

### LIN
- **Status:** active
- **Purpose:** lineage issuance and completeness authority.
- **Failure Prevented:** promotion without provenance/lineage continuity.
- **Signal Improved:** artifact traceability completeness.
- **Canonical Artifacts Owned:** `artifact_lineage_record`, `lineage_issuance_registry_record`, `lineage_authenticity_result`.
- **Upstream Dependencies:** all artifact producers.
- **Downstream Dependencies:** CDE, GOV, REP.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/artifact_lineage.py`
  - `spectrum_systems/modules/runtime/lineage_issuance_registry.py`
  - `spectrum_systems/modules/runtime/lineage_authenticity.py`

### OBS
- **Status:** active
- **Purpose:** observability contract and completeness authority.
- **Failure Prevented:** hidden failures and unmeasurable control outcomes.
- **Signal Improved:** metric/log/trace completeness.
- **Canonical Artifacts Owned:** `observability_metrics_record`, `trace_store_record`, `alert_trigger_record`.
- **Upstream Dependencies:** PQX/EVL/CDE/SEL telemetry.
- **Downstream Dependencies:** SLO, FRE, GOV.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/observability_metrics.py`
  - `spectrum_systems/modules/runtime/trace_store.py`
  - `spectrum_systems/modules/runtime/alert_triggers.py`

### SLO
- **Status:** active
- **Purpose:** error-budget and burn-rate authority.
- **Failure Prevented:** silent reliability degradation without control response.
- **Signal Improved:** budget adherence and reliability trend clarity.
- **Canonical Artifacts Owned:** `slo_control_record`, `slo_enforcement_record`, `budget_burn_alert`.
- **Upstream Dependencies:** OBS metrics.
- **Downstream Dependencies:** TPA, CDE, SEL.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/slo_control.py`
  - `spectrum_systems/modules/runtime/slo_enforcement.py`
  - `spectrum_systems/modules/runtime/slo_enforcer.py`

### CTX
- **Status:** active
- **Purpose:** context-bundle governance for retrieve, normalization, and transformation admission.
- **Failure Prevented:** malformed/irrelevant context admitted into execution.
- **Signal Improved:** context quality and admission determinism.
- **Canonical Artifacts Owned:** `context_bundle`, `context_admission_record`, `context_transform_record`.
- **Upstream Dependencies:** retrieve/query pipelines and input adapters.
- **Downstream Dependencies:** AEX, PQX, RIL.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/ctx.py`
  - `spectrum_systems/modules/runtime/context_governed_flow.py`
  - `spectrum_systems/modules/runtime/preflight_failure_normalizer.py`

### PRM
- **Status:** active
- **Purpose:** prompt/task registry governance for admissible execution intents.
- **Failure Prevented:** unregistered prompt/task execution and ambiguous intent versions.
- **Signal Improved:** prompt/task provenance and admissibility confidence.
- **Canonical Artifacts Owned:** `task_registry_record`, `prompt_admission_record`.
- **Upstream Dependencies:** governance inputs, authored tasks/prompts.
- **Downstream Dependencies:** AEX, TLC.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/task_registry.py`
  - `spectrum_systems/modules/runtime/routing_policy.py`

### POL
- **Status:** active
- **Purpose:** policy lifecycle and rollout governance.
- **Failure Prevented:** unmanaged policy rollout/canary drift.
- **Signal Improved:** policy rollout safety and regression visibility.
- **Canonical Artifacts Owned:** `policy_registry_record`, `rollout_gate_result`, `canary_release_record`.
- **Upstream Dependencies:** governance policy authoring.
- **Downstream Dependencies:** TPA, GOV.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/policy_registry.py`
  - `spectrum_systems/modules/runtime/pol_runtime.py`
  - `spectrum_systems/modules/runtime/rollout_gate.py`

### TLC
- **Status:** active
- **Purpose:** top-level orchestration and routing authority across subsystems.
- **Failure Prevented:** orphaned execution requests and route ambiguity.
- **Signal Improved:** routing determinism and orchestration state visibility.
- **Canonical Artifacts Owned:** `top_level_conductor_run_artifact`, `route_decision_record`.
- **Upstream Dependencies:** AEX admission and PRM routes.
- **Downstream Dependencies:** PQX and supporting systems.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/top_level_conductor.py`
  - `spectrum_systems/modules/runtime/tlc_hardening.py`
  - `spectrum_systems/modules/runtime/route_policy.py`

### RIL
- **Status:** active
- **Purpose:** interpretation layer for review/runtime signals.
- **Failure Prevented:** unstructured findings entering control decisions.
- **Signal Improved:** interpretation consistency and semantic traceability.
- **Canonical Artifacts Owned:** `review_interpretation_record`, `signal_mapping_record`.
- **Upstream Dependencies:** OBS, EVL, review inputs.
- **Downstream Dependencies:** FRE, CDE, JDX.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/ril_interpretation.py`
  - `spectrum_systems/modules/runtime/review_parsing_engine.py`

### FRE
- **Status:** active
- **Purpose:** failure diagnosis and repair planning authority.
- **Failure Prevented:** repeated failures without structured root-cause/repair plans.
- **Signal Improved:** diagnosis precision and repair effectiveness.
- **Canonical Artifacts Owned:** `failure_diagnosis_record`, `repair_plan_artifact`.
- **Upstream Dependencies:** REP, OBS, RIL.
- **Downstream Dependencies:** PQX, CDE, GOV.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/failure_diagnosis_engine.py`
  - `spectrum_systems/modules/runtime/fre_repair_flow.py`

### RAX
- **Status:** active
- **Purpose:** bounded runtime candidate-signal intelligence surface (non-decisioning).
- **Failure Prevented:** opaque candidate-signal generation without governance boundaries.
- **Signal Improved:** candidate runtime signal quality and calibration visibility.
- **Canonical Artifacts Owned:** `runtime_candidate_signal`, `rax_eval_result`.
- **Upstream Dependencies:** runtime telemetry and model outputs.
- **Downstream Dependencies:** EVL, RIL, FRE.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/rax_model.py`
  - `spectrum_systems/modules/runtime/rax_eval_runner.py`

### RSM
- **Status:** active
- **Purpose:** reconciliation state manager for desired-vs-actual state artifacts.
- **Failure Prevented:** unresolved drift between intended and observed system state.
- **Signal Improved:** reconciliation completeness and state-drift transparency.
- **Canonical Artifacts Owned:** `reconciliation_state_record`, `drift_reconciliation_plan`.
- **Upstream Dependencies:** OBS, REP.
- **Downstream Dependencies:** CDE, FRE.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/drift_detection_engine.py`
  - `spectrum_systems/modules/runtime/maintain_drift.py`

### CAP
- **Status:** active
- **Purpose:** capacity/cost governance authority.
- **Failure Prevented:** uncontrolled runtime budget and latency overruns.
- **Signal Improved:** cost and capacity budget adherence.
- **Canonical Artifacts Owned:** `capacity_budget_record`, `cost_control_signal`.
- **Upstream Dependencies:** OBS metrics, execution traces.
- **Downstream Dependencies:** TLC, TPA.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/platform_reliability_ops.py`
  - `spectrum_systems/modules/runtime/qos_runtime.py`

### SEC
- **Status:** active
- **Purpose:** security boundary governance and guardrail-control integration.
- **Failure Prevented:** unsafe permission/identity bypass in governed execution.
- **Signal Improved:** security control coverage and policy conformance.
- **Canonical Artifacts Owned:** `permission_governance_record`, `identity_enforcement_record`, `downstream_guard_record`.
- **Upstream Dependencies:** policy registry and trust decisions.
- **Downstream Dependencies:** TPA, SEL.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/permission_governance.py`
  - `spectrum_systems/modules/runtime/identity_enforcement.py`
  - `spectrum_systems/modules/runtime/downstream_a2a_guard.py`

### JDX
- **Status:** active
- **Purpose:** judgment artifact semantics and decision-application authority.
- **Failure Prevented:** ambiguous judgment artifact semantics in control use.
- **Signal Improved:** judgment evidence-to-decision mapping integrity.
- **Canonical Artifacts Owned:** `judgment_record`, `judgment_policy_candidate`, `judgment_application_record`.
- **Upstream Dependencies:** RIL and EVL signals.
- **Downstream Dependencies:** CDE, GOV, JSX.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/judgment_engine.py`
  - `spectrum_systems/modules/runtime/pqx_judgment.py`
  - `spectrum_systems/modules/runtime/judgment_policy_candidates.py`

### JSX
- **Status:** active
- **Purpose:** judgment lifecycle/supersession/retirement active-set authority.
- **Failure Prevented:** stale or conflicting judgments remaining active.
- **Signal Improved:** active-set correctness and lifecycle transparency.
- **Canonical Artifacts Owned:** `judgment_lifecycle_record`, `judgment_supersession_record`, `judgment_retirement_record`.
- **Upstream Dependencies:** JDX judgment artifacts.
- **Downstream Dependencies:** CDE, GOV.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/jsx.py`
  - `spectrum_systems/modules/runtime/judgment_learning.py`

### PRA
- **Status:** active
- **Purpose:** promotion-readiness authority.
- **Failure Prevented:** promotion without explicit readiness checkpointing.
- **Signal Improved:** promotion readiness confidence and traceability.
- **Canonical Artifacts Owned:** `promotion_readiness_checkpoint`, `pr_readiness_record`.
- **Upstream Dependencies:** CDE, EVL, LIN.
- **Downstream Dependencies:** GOV.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/promotion_readiness_checkpoint.py`
  - `spectrum_systems/modules/runtime/pra_nsx_prg_loop.py`

### GOV
- **Status:** active
- **Purpose:** certification/governance gate authority.
- **Failure Prevented:** uncertified promotion and policy-incomplete closure.
- **Signal Improved:** certification gate integrity.
- **Canonical Artifacts Owned:** `governance_gate_result`, `certification_record`, `governance_remediation_record`.
- **Upstream Dependencies:** CDE, PRA, POL, LIN.
- **Downstream Dependencies:** SEL, roadmap/control loops.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/continuous_governance.py`
  - `spectrum_systems/modules/runtime/governance_chain_guard.py`

### MAP
- **Status:** active
- **Purpose:** metadata/topology/system-map authority for runtime projections.
- **Failure Prevented:** inconsistent system-map mediation and projection mismatch.
- **Signal Improved:** topology projection consistency.
- **Canonical Artifacts Owned:** `system_map_projection`, `metadata_topology_record`.
- **Upstream Dependencies:** registry and runtime metadata producers.
- **Downstream Dependencies:** TLC, GOV.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/meta_governance_kernel.py`
  - `spectrum_systems/modules/runtime/review_projection_adapter.py`

## Merged or demoted systems

| System | Status | Merged/Demoted Into | Rationale |
| --- | --- | --- | --- |
| SUP | merged | JSX | Active-set governance belongs to judgment lifecycle authority. |
| RET | merged | JSX | Retirement/deprecation lifecycle is a JSX lifecycle responsibility. |
| QRY | merged | CTX | Retrieval/query admission now governed as part of context admission. |
| NRM | merged | CTX | Normalization is a context-governance sub-capability, not top-level authority. |
| TRN | merged | CTX | Translation/transformation for admission is retained under CTX. |
| CMP | merged | EVL | Comparison runs are evaluation artifact families, not separate authorities. |
| RSK | merged | EVL | Risk classification is part of eval outputs and gate criteria. |
| HNX | deprecated | Artifact family | Stage harness semantics retained as support execution scaffolding. |
| MNT | deprecated | Review label | Maintain phase remains a cross-system label, not authority owner. |
| RWA | deprecated | Artifact family | Owner-surface recording retained as supporting metadata capability. |
| MCL | deprecated | Artifact family | Memory compaction is a supporting artifact method, not authority. |
| DCL | deprecated | Artifact family | Doctrine compilation retained as support documentation capability. |
| DEM | deprecated | Review label | Decision economics remains advisory only; not an executable authority. |

## Future / placeholder systems

| System | Status | Rationale |
| --- | --- | --- |
| ABX | future | Placeholder exchange seam; no bounded executable authority in runtime modules. |
| DBB | future | Placeholder data-backbone seam; no canonical executable owner implementation. |
| LCE | future | Lifecycle concept appears in docs, but no dedicated authority module. |
| SAL | future | Source authority abstraction remains conceptual at current scope. |
| SAS | future | Source sync ingestion not yet a discrete bounded authority. |
| SHA | future | Shared authority placeholder; no runtime owner module boundary. |
| SIV | future | Reserved acronym only; intentionally non-active. |

## Artifact families and supporting capabilities (non-authority)

These are important but non-top-level authority families:

- **Eval support families:** comparison artifacts, risk artifacts, synthesized summaries.
- **Judgment support families:** evidence sufficiency, explainability, handoff artifacts.
- **Operational support families:** canary/release operations, queue/load telemetry, dependency graph diagnostics.
- **Review labels/methods:** maintain-stage labels (MNT), doctrine/memory methods (DCL/MCL), decision economics review labels (DEM).

## Boundary clarifications

- **TLC vs PQX:** TLC routes/orchestrates execution; PQX executes bounded work.
- **JDX vs JSX:** JDX owns judgment artifact semantics/application; JSX owns lifecycle, supersession, retirement, and active-set correctness.
- **TPA vs CDE vs SEL:** TPA adjudicates trust/policy; CDE decides closure/readiness; SEL executes fail-closed enforcement actions.
- **RAX resolution:** RAX is **active** because runtime implementation exists (`rax_model.py`, `rax_eval_runner.py`) and provides bounded candidate-signal artifacts without decision authority.

## System Map
- **AEX** — active admission and execution exchange authority
- **PQX** — active bounded execution authority
- **EVL** — active evaluation and eval-gate authority
- **TPA** — active trust and policy adjudication authority
- **CDE** — active control and closure decision authority
- **SEL** — active enforcement authority
- **REP** — active replay integrity authority
- **LIN** — active lineage authority
- **OBS** — active observability authority
- **SLO** — active SLO and error-budget authority
- **CTX** — active context governance authority
- **PRM** — active prompt/task registry governance authority
- **POL** — active policy lifecycle governance authority
- **TLC** — active orchestration and routing authority
- **RIL** — active interpretation authority
- **FRE** — active failure diagnosis and repair planning authority
- **RAX** — active bounded runtime candidate-signal authority
- **RSM** — active reconciliation state management authority
- **CAP** — active capacity and cost governance authority
- **SEC** — active security boundary governance authority
- **JDX** — active judgment artifact/application authority
- **JSX** — active judgment lifecycle authority
- **PRA** — active promotion readiness authority
- **GOV** — active certification and governance gate authority
- **MAP** — active metadata/topology authority
- **SUP** — deprecated merged into JSX supersession lifecycle
- **RET** — deprecated merged into JSX retirement lifecycle
- **QRY** — deprecated merged into CTX retrieve admission flow
- **NRM** — deprecated merged into CTX normalization flow
- **TRN** — deprecated merged into CTX transformation flow
- **CMP** — deprecated merged into EVL comparison artifact family
- **RSK** — deprecated merged into EVL risk artifact family
- **HNX** — deprecated support harness capability
- **MNT** — deprecated recurring review label
- **RWA** — deprecated supporting metadata capability
- **MCL** — deprecated artifact family capability
- **DCL** — deprecated artifact family capability
- **DEM** — deprecated review label capability
- **ABX** — placeholder future exchange seam
- **DBB** — placeholder future data backbone seam
- **LCE** — placeholder future lifecycle seam
- **SAL** — placeholder future source authority seam
- **SAS** — placeholder future source sync seam
- **SHA** — placeholder future shared authority seam
- **SIV** — not currently present in this repository scope (reserved acronym)

## System Definitions

### AEX
- **acronym:** `AEX`
- **full_name:** Admission and Execution Exchange
- **role:** bounded admission boundary for execution.
- **owns:**
  - aex_admission_boundary
- **consumes:**
  - execution_request
- **produces:**
  - admission_record
- **must_not_do:**
  - execute_bounded_work

### PQX
- **acronym:** `PQX`
- **full_name:** Prompt Queue Execution
- **role:** bounded execution engine.
- **owns:**
  - pqx_execution_authority
- **consumes:**
  - admitted_execution_request
- **produces:**
  - execution_record
- **must_not_do:**
  - adjudicate_trust_policy

### EVL
- **acronym:** `EVL`
- **full_name:** Evaluation Gate Authority
- **role:** evaluation coverage and gate authority.
- **owns:**
  - evl_required_evaluation_gate
- **consumes:**
  - execution_record
- **produces:**
  - evaluation_gate_result
- **must_not_do:**
  - issue_closure_decision

### TPA
- **acronym:** `TPA`
- **full_name:** Trust Policy Authority
- **role:** trust and policy adjudication authority.
- **owns:**
  - tpa_policy_adjudication
- **consumes:**
  - evaluation_gate_result
- **produces:**
  - trust_policy_decision
- **must_not_do:**
  - enforce_actions_directly

### CDE
- **acronym:** `CDE`
- **full_name:** Closure Decision Engine
- **role:** closure/readiness control decision authority.
- **owns:**
  - cde_closure_decision
- **consumes:**
  - trust_policy_decision
- **produces:**
  - closure_decision_artifact
- **must_not_do:**
  - execute_enforcement_actions

### SEL
- **acronym:** `SEL`
- **full_name:** System Enforcement Layer
- **role:** fail-closed enforcement authority.
- **owns:**
  - sel_enforcement_execution
- **consumes:**
  - closure_decision_artifact
- **produces:**
  - enforcement_action_record
- **must_not_do:**
  - issue_policy_decisions

### REP
- **acronym:** `REP`
- **full_name:** Replay Authority
- **role:** deterministic replay integrity authority.
- **owns:**
  - rep_replay_integrity
- **consumes:**
  - execution_record
- **produces:**
  - replay_record
- **must_not_do:**
  - bypass_lineage_requirements

### LIN
- **acronym:** `LIN`
- **full_name:** Lineage Authority
- **role:** lineage issuance and completeness authority.
- **owns:**
  - lin_lineage_completeness
- **consumes:**
  - governed_artifacts
- **produces:**
  - lineage_record
- **must_not_do:**
  - waive_promotion_lineage_gate

### OBS
- **acronym:** `OBS`
- **full_name:** Observability Authority
- **role:** observability completeness authority.
- **owns:**
  - obs_observability_completeness
- **consumes:**
  - runtime_signals
- **produces:**
  - observability_record
- **must_not_do:**
  - substitute_for_control_decisions

### SLO
- **acronym:** `SLO`
- **full_name:** Service Level Objectives Authority
- **role:** error-budget governance authority.
- **owns:**
  - slo_error_budget_control
- **consumes:**
  - observability_record
- **produces:**
  - slo_control_record
- **must_not_do:**
  - bypass_fail_closed_policy

### CTX
- **acronym:** `CTX`
- **full_name:** Context Governance
- **role:** context admission/normalization/transformation authority.
- **owns:**
  - ctx_context_admission
- **consumes:**
  - retrieved_context_inputs
- **produces:**
  - context_bundle
- **must_not_do:**
  - issue_control_closure

### PRM
- **acronym:** `PRM`
- **full_name:** Prompt Registry Management
- **role:** prompt/task registry governance authority.
- **owns:**
  - prm_prompt_registry_admission
- **consumes:**
  - authored_prompts
- **produces:**
  - prompt_registry_record
- **must_not_do:**
  - execute_runtime_work

### POL
- **acronym:** `POL`
- **full_name:** Policy Lifecycle Governance
- **role:** policy lifecycle and rollout authority.
- **owns:**
  - pol_policy_rollout_governance
- **consumes:**
  - policy_change_requests
- **produces:**
  - rollout_gate_record
- **must_not_do:**
  - override_tpa_adjudication

### TLC
- **acronym:** `TLC`
- **full_name:** Top Level Conductor
- **role:** top-level orchestration and routing authority.
- **owns:**
  - tlc_orchestration_routing
- **consumes:**
  - admitted_requests
- **produces:**
  - route_decision_record
- **must_not_do:**
  - execute_slice_payloads

### RIL
- **acronym:** `RIL`
- **full_name:** Runtime Interpretation Layer
- **role:** interpretation and structured signal mapping authority.
- **owns:**
  - ril_signal_interpretation
- **consumes:**
  - review_runtime_signals
- **produces:**
  - interpretation_record
- **must_not_do:**
  - enforce_runtime_actions

### FRE
- **acronym:** `FRE`
- **full_name:** Failure Repair Engine
- **role:** failure diagnosis and repair planning authority.
- **owns:**
  - fre_failure_diagnosis_planning
- **consumes:**
  - replay_and_observability_records
- **produces:**
  - repair_plan_artifact
- **must_not_do:**
  - self_promote_artifacts

### RAX
- **acronym:** `RAX`
- **full_name:** Runtime Analysis eXchange
- **role:** bounded runtime candidate-signal authority.
- **owns:**
  - rax_candidate_signal_surface
- **consumes:**
  - runtime_candidate_inputs
- **produces:**
  - runtime_candidate_signal
- **must_not_do:**
  - issue_authoritative_control_decisions

### RSM
- **acronym:** `RSM`
- **full_name:** Reconciliation State Manager
- **role:** desired-vs-actual reconciliation authority.
- **owns:**
  - rsm_reconciliation_state
- **consumes:**
  - drift_signals
- **produces:**
  - reconciliation_record
- **must_not_do:**
  - bypass_governance_gates

### CAP
- **acronym:** `CAP`
- **full_name:** Capacity Governance
- **role:** cost/capacity governance authority.
- **owns:**
  - cap_capacity_budget_control
- **consumes:**
  - runtime_utilization_signals
- **produces:**
  - capacity_budget_record
- **must_not_do:**
  - override_policy_gates

### SEC
- **acronym:** `SEC`
- **full_name:** Security Boundary Governance
- **role:** security boundary and guardrail governance authority.
- **owns:**
  - sec_security_boundary_control
- **consumes:**
  - identity_permission_signals
- **produces:**
  - security_boundary_record
- **must_not_do:**
  - bypass_enforcement_layer

### JDX
- **acronym:** `JDX`
- **full_name:** Judgment Artifact Authority
- **role:** judgment artifact semantics/application authority.
- **owns:**
  - jdx_judgment_artifact_semantics
- **consumes:**
  - interpreted_eval_signals
- **produces:**
  - judgment_record
- **must_not_do:**
  - manage_lifecycle_supersession

### JSX
- **acronym:** `JSX`
- **full_name:** Judgment Lifecycle Authority
- **role:** judgment lifecycle/supersession/retirement authority.
- **owns:**
  - jsx_judgment_lifecycle_control
- **consumes:**
  - judgment_record
- **produces:**
  - judgment_lifecycle_record
- **must_not_do:**
  - redefine_judgment_artifact_semantics

### PRA
- **acronym:** `PRA`
- **full_name:** Promotion Readiness Authority
- **role:** promotion readiness checkpoint authority.
- **owns:**
  - pra_promotion_readiness_gate
- **consumes:**
  - closure_decision_artifact
- **produces:**
  - promotion_readiness_record
- **must_not_do:**
  - certify_governance_readiness

### GOV
- **acronym:** `GOV`
- **full_name:** Governance Certification Authority
- **role:** certification/governance gate authority.
- **owns:**
  - gov_certification_gate
- **consumes:**
  - promotion_readiness_record
- **produces:**
  - governance_gate_result
- **must_not_do:**
  - execute_work_slices

### MAP
- **acronym:** `MAP`
- **full_name:** Metadata Authority Plane
- **role:** metadata/topology/system-map authority.
- **owns:**
  - map_topology_projection_authority
- **consumes:**
  - registry_and_runtime_metadata
- **produces:**
  - metadata_topology_record
- **must_not_do:**
  - override_control_authorities

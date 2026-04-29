# System Registry (Canonical)

## Core rules
1. **Artifact-first execution:** every stage consumes and emits governed artifact records.
2. **Fail-closed behavior:** missing lineage, eval coverage, policy clarity, or control decisions blocks progression.
3. **Promotion requires certification:** promotion readiness and certification remain explicit authority decisions.

## Canonical loop

`AEX → PQX → EVL → TPA → CDE → SEL`

Overlay authorities required in the same loop:

`REP + LIN + OBS + SLO`

## Measurement and observability layer (non-authority)

A non-owning measurement layer over the canonical loop and per-system
behavior is documented in
`docs/architecture/3ls_measurement_layer.md`. Its artifacts
(`3ls_system_measurement_record`, `3ls_loop_run_record`,
`3ls_handoff_record`, `3ls_surface_coverage_record`,
`3ls_failure_recurrence_record`, `3ls_trust_gap_closure_record`,
`3ls_replayability_record`, `3ls_scope_risk_record`,
`3ls_operator_debuggability_record`) are observation only — they do not
grant authority, replace control decisions, or perform enforcement, and
they feed OBS / LIN / REP / SLO.

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

### MET
- **Status:** active, non-owning
- **Purpose:** measurement, explanation, recommendation, closure tracking, outcome attribution, and signal integrity. MET observes the governed loop, compresses signals, and emits readiness/owner-handoff inputs. It does not decide, approve, enforce, certify, promote, execute, or admit.
- **Failure Prevented:**
  - undetected bottlenecks
  - unclear failure causes
  - stale candidates
  - fake trends
  - unverified improvements
  - overconfident recommendations
  - recurring failures
  - metric gaming
- **Signal Improved:**
  - debuggability
  - bottleneck clarity
  - closure visibility
  - outcome attribution
  - recommendation calibration
  - signal integrity
- **Authority:** NONE
- **Forbidden:** decision ownership, approval ownership, enforcement ownership, certification ownership, promotion ownership, execution ownership, admission ownership.
- **Invariant:** if MET produces an authority outcome, block. MET artifacts surface observations, recommendations, signals, and readiness evidence only.
- **Canonical Artifacts Owned:** non-authority `dashboard_metrics/*` measurement, observation, and signal records (e.g. `candidate_closure_ledger_record`, `outcome_attribution_record`, `recommendation_accuracy_record`, `signal_integrity_check_record`).
- **Upstream Dependencies:** EVL, LIN, REP, OBS, SLO, TPA, CDE, SEL artifacts.
- **Downstream Consumers:** AEX, PQX, EVL, TPA, CDE, SEL, GOV, dashboard-3ls.
- **Primary Code Paths:**
  - `apps/dashboard-3ls/app/api/intelligence/route.ts`
  - `apps/dashboard-3ls/app/page.tsx`
  - `artifacts/dashboard_metrics/`

### HOP
- **Status:** active
- **Purpose:** harness optimization substrate — stores candidate harness code,
  scores, traces, and failure hypotheses; orchestrates candidate evaluation
  against a versioned eval set; exposes a queryable, replay-compatible
  history. A bounded proposer module emits candidate harness code from
  deterministic mutation templates; it is admission-gated, sandboxed, and
  advisory-only — it never persists artifacts, never invokes the evaluator,
  and never advances candidates. An AI failure mapper module converts
  recurring AI/coding-agent failure patterns into bounded, advisory
  system-improvement proposals targeting specific 3-letter systems; all
  proposals are advisory-only and require CDE/GOV approval before any
  mutation can occur (see `docs/reviews/hop_batch4_review.md` and
  `docs/architecture/system_registry.md` authority boundaries).
- **Failure Prevented:** ungoverned harness experimentation, eval gaming,
  loss of failure provenance, free-form harness output dependencies, and
  recurring AI/agent failure patterns without a governed improvement path.
- **Signal Improved:** harness candidate quality visibility, frontier
  transparency, eval-set integrity, and target-system improvement signal
  derived from observed AI failure patterns.
- **Canonical Artifacts Owned:** `hop_harness_candidate`, `hop_harness_run`,
  `hop_harness_score`, `hop_harness_trace`, `hop_harness_frontier`,
  `hop_harness_failure_hypothesis`, `hop_harness_eval_case`,
  `hop_harness_faq_output`, `hop_harness_ai_failure_pattern`,
  `hop_harness_system_improvement_proposal`.
- **Upstream Dependencies:** EVL (eval-set policy alignment), CTX (transcript
  context governance for input shape).
- **Downstream Dependencies:** EVL (eval surface contributions and scope_adherence
  eval cases from improvement proposals), FRE (failure-derived candidates feed
  FRE diagnosis only via governed adoption), CDE (control authority external to
  HOP — HOP never decides promotion; improvement proposals require CDE/GOV
  review), RDX (receives split-requirement signals from over-scoped execution
  proposals — advisory only), HNX (receives checkpoint-requirement signals from
  missing-checkpoint proposals — advisory only), SEL (receives compliance signals
  from improvement proposals — SEL retains all signal-gate ownership).
- **Primary Code Paths:**
  - `spectrum_systems/modules/hop/experience_store.py`
  - `spectrum_systems/modules/hop/evaluator.py`
  - `spectrum_systems/modules/hop/validator.py`
  - `spectrum_systems/modules/hop/safety_checks.py`
  - `spectrum_systems/modules/hop/frontier.py`
  - `spectrum_systems/modules/hop/baseline_harness.py`
  - `spectrum_systems/modules/hop/proposer.py`
  - `spectrum_systems/modules/hop/mutation_policy.py`
  - `spectrum_systems/modules/hop/optimization_loop.py`
  - `spectrum_systems/modules/hop/sandbox.py`
  - `spectrum_systems/modules/hop/control_integration.py`
  - `spectrum_systems/modules/hop/ai_failure_mapper.py`
  - readiness_signal builder and rollback_signal emitter modules under
    `spectrum_systems/modules/hop/` (filenames retained for git history;
    advisory-only — see `docs/reviews/hop005_authority_eval_hardening_review.md`)
  - `spectrum_systems/cli/hop_cli.py`

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
- **HOP** — active harness optimization substrate authority
- **MET** — active non-owning measurement, observation, and signal-integrity capability (no authority)
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
- **HNX** — stage harness support capability
- **XRL** — external reality loop support capability
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


## Repo mutation entry invariants
- All Codex execution requests that create or modify repository state MUST enter through **AEX**.
- **PQX** MUST reject repo-writing execution that lacks AEX admission artifacts plus TLC-mediated lineage.
- Any attempt to invoke **TLC** or **PQX** directly for repo-mutating work without valid AEX/TLC lineage MUST fail closed.

## Recurring Cross-System Phase Labels (Non-Owner)

### MNT — Maintain / Cross-System Trust Integration
- **classification:** recurring phase label (not a canonical system owner)
- **status:** non_owner_phase_label
- **role:** maintain-stage cross-system trust integration label only.
- **owns:**
  - maintain_phase_label
- **consumes:**
  - trust_health_inputs
- **produces:**
  - mnt_maintain_cycle_report
- **must_not_do:**
  - own_policy_authority
  - own_execution_authority
  - own_control_authority
  - own_enforcement_authority

## System Definitions

### AEX
- **role:** admission boundary.
- **status:** active
- **owns:**
  - execution_admission
  - request_validation
  - entrypoint_enforcement
- **consumes:**
  - codex_build_request
- **produces:**
  - build_admission_record
- **must_not_do:**
  - execute_work

### PQX
- **role:** execution engine.
- **status:** active
- **owns:**
  - execution
  - execution_state_transitions
  - execution_trace_emission
- **consumes:**
  - codex_pqx_task_wrapper
- **produces:**
  - agent_execution_trace
- **must_not_do:**
  - issue_closure_state_decisions

### HNX
- **role:** harness semantics.
- **status:** demoted
- **owns:**
  - harness_stage_semantics
- **consumes:**
  - stage_contract
- **produces:**
  - checkpoint_record
- **must_not_do:**
  - execute_work

### MAP
- **role:** mediation projection.
- **status:** active
- **owns:**
  - mediation_projection_formatting
- **consumes:**
  - review_integration_packet_artifact
- **produces:**
  - map_projection_record
- **must_not_do:**
  - reinterpret_review_semantics

### RDX
- **role:** roadmap exchange.
- **status:** demoted
- **owns:**
  - roadmap_execution_governance
- **consumes:**
  - roadmap_inputs
- **produces:**
  - rdx_roadmap_governance_bundle
- **must_not_do:**
  - execute_runtime_work

### TPA
- **role:** trust policy gate.
- **status:** active
- **owns:**
  - trust_policy_application
  - scope_gating
- **consumes:**
  - evaluation_control_decision
- **produces:**
  - control_arbitration_record
- **must_not_do:**
  - execute_enforcement

### FRE
- **role:** repair planning.
- **status:** active
- **owns:**
  - failure_diagnosis
  - repair_plan_generation
- **consumes:**
  - failure_signals
- **produces:**
  - fre_multi_step_repair_plan_record
- **must_not_do:**
  - issue_promotion_decisions

### RIL
- **role:** interpretation layer.
- **status:** active
- **owns:**
  - review_interpretation
- **consumes:**
  - review_signals
- **produces:**
  - interpretation_record
- **must_not_do:**
  - issue_control_decisions

### RQX
- **role:** review queue.
- **status:** demoted
- **owns:**
  - review_queue_execution
  - bounded_fix_request_emission
  - unresolved_post_cycle_operator_handoff_emission
- **consumes:**
  - review_artifacts
- **produces:**
  - control_loop_review_queue_record_artifact
- **must_not_do:**
  - own_review_interpretation

### SEL
- **role:** enforcement layer.
- **status:** active
- **owns:**
  - enforcement
  - fail_closed_blocking
  - promotion_guarding
- **consumes:**
  - closure_decision_artifact
- **produces:**
  - control_surface_enforcement_result
- **must_not_do:**
  - interpret_policy

### CDE
- **role:** closure decision engine.
- **status:** active
- **owns:**
  - closure_decisions
  - promotion_readiness_decisioning
  - closure_lock_state
- **consumes:**
  - trust_policy_decision
- **produces:**
  - closure_decision_artifact
- **must_not_do:**
  - execute_enforcement

### TLC
- **role:** orchestration layer.
- **status:** active
- **owns:**
  - orchestration
  - subsystem_routing
  - bounded_cycle_coordination
  - unresolved_handoff_disposition_classification
- **consumes:**
  - build_admission_record
- **produces:**
  - aex_tlc_handoff_integrity_record
- **must_not_do:**
  - own_closure_decisions

### PRG
- **role:** program governance.
- **status:** demoted
- **owns:**
  - program_governance
  - roadmap_alignment
  - program_drift_management
- **consumes:**
  - roadmap_inputs
- **produces:**
  - prg_governance_bundle
- **must_not_do:**
  - own_runtime_execution

### RSM
- **role:** reconciliation state.
- **status:** active
- **owns:**
  - reconciliation_state_records
- **consumes:**
  - state_deltas
- **produces:**
  - rsm_divergence_record
- **must_not_do:**
  - own_closure_authority

### RAX
- **role:** runtime candidate signals.
- **status:** active
- **owns:**
  - runtime_candidate_signal_records
- **consumes:**
  - runtime_candidate_inputs
- **produces:**
  - rax_health_snapshot
- **must_not_do:**
  - issue_control_decisions

### XRL
- **role:** external reality loop support.
- **status:** demoted
- **owns:**
  - external_reality_loop_records
- **consumes:**
  - outcome_feedback_inputs
- **produces:**
  - xrl_real_world_outcome_integration_record
- **must_not_do:**
  - own_policy_authority

### CHX
- **role:** chaos harness.
- **status:** demoted
- **owns:**
  - chaos_injection_artifacts
- **consumes:**
  - failure_signals
- **produces:**
  - chx_injection_record
- **must_not_do:**
  - own_runtime_execution

### DEX
- **role:** decision explainability.
- **status:** demoted
- **owns:**
  - decision_explainability_records
- **consumes:**
  - decision_artifacts
- **produces:**
  - artifact_diff_record
- **must_not_do:**
  - own_closure_decisions

### SIM
- **role:** simulation.
- **status:** demoted
- **owns:**
  - simulation_candidate_records
- **consumes:**
  - policy_candidates
- **produces:**
  - simx_replayable_bundle
- **must_not_do:**
  - own_live_state_mutation

### PRX
- **role:** precedent retrieval.
- **status:** demoted
- **owns:**
  - precedent_retrieval_records
- **consumes:**
  - historical_artifacts
- **produces:**
  - prompt_queue_replay_record
- **must_not_do:**
  - own_closure_authority

### CVX
- **role:** cross-run validation.
- **status:** demoted
- **owns:**
  - cross_run_consistency_records
- **consumes:**
  - run_outputs
- **produces:**
  - comparison_run_record
- **must_not_do:**
  - own_execution_mutation

### HIX
- **role:** human interaction.
- **status:** demoted
- **owns:**
  - human_interaction_exchange_records
- **consumes:**
  - override_requests
- **produces:**
  - override_governance_record
- **must_not_do:**
  - own_bypass_behaviors

### CAL
- **role:** calibration.
- **status:** demoted
- **owns:**
  - calibration_records
- **consumes:**
  - confidence_signals
- **produces:**
  - cal_calibration_record
- **must_not_do:**
  - own_policy_authority

### POL
- **role:** policy lifecycle.
- **status:** active
- **owns:**
  - policy_rollout_lifecycle
- **consumes:**
  - policy_change_requests
- **produces:**
  - pol_rollout_record
- **must_not_do:**
  - decide_live_policy_authority

### AIL
- **role:** artifact intelligence.
- **status:** demoted
- **owns:**
  - artifact_intelligence_records
- **consumes:**
  - artifact_signals
- **produces:**
  - ail_index_record
- **must_not_do:**
  - own_control_decisions

### SCH
- **role:** schema compatibility.
- **status:** demoted
- **owns:**
  - schema_compatibility_records
- **consumes:**
  - schema_change_inputs
- **produces:**
  - con_compatibility_gate_result
- **must_not_do:**
  - own_execution_authority

### DEP
- **role:** dependency reliability.
- **status:** demoted
- **owns:**
  - dependency_chain_validation_records
- **consumes:**
  - dependency_graph_artifacts
- **produces:**
  - dep_chain_break_replay_probe_pack
- **must_not_do:**
  - own_control_decisions

### RCA
- **role:** root cause.
- **status:** demoted
- **owns:**
  - root_cause_attribution_records
- **consumes:**
  - failure_evidence
- **produces:**
  - replay_decision_analysis
- **must_not_do:**
  - own_enforcement_authority

### QOS
- **role:** queue governance.
- **status:** demoted
- **owns:**
  - queue_budget_governance_records
- **consumes:**
  - queue_signals
- **produces:**
  - qos_queue_governance_record
- **must_not_do:**
  - own_policy_authority

### SIMX
- **role:** simulation replay.
- **status:** demoted
- **owns:**
  - simulation_replay_integrity_records
- **consumes:**
  - simulation_runs
- **produces:**
  - simx_replayable_bundle
- **must_not_do:**
  - own_runtime_mutation

### JDX
- **role:** judgment semantics.
- **status:** active
- **owns:**
  - judgment_artifact_requirements
  - judgment_record
- **consumes:**
  - interpreted_eval_signals
- **produces:**
  - jdx_judgment_record
- **must_not_do:**
  - own_closure_authority

### JSX
- **role:** judgment lifecycle.
- **status:** active
- **owns:**
  - judgment_lifecycle_rules
- **consumes:**
  - judgment_record
- **produces:**
  - judgment_lifecycle_record
- **must_not_do:**
  - own_judgment_semantics

### RUX
- **role:** reuse governance.
- **status:** demoted
- **owns:**
  - reuse_record_artifacts
- **consumes:**
  - artifact_reuse_inputs
- **produces:**
  - artifact_family_health_report
- **must_not_do:**
  - own_control_decisions

### XPL
- **role:** explainability governance.
- **status:** demoted
- **owns:**
  - artifact_card_records
- **consumes:**
  - artifact_inputs
- **produces:**
  - artifact_intelligence_report
- **must_not_do:**
  - own_closure_authority

### REL
- **role:** release governance.
- **status:** demoted
- **owns:**
  - canary_rollout_artifacts
  - release_records
- **consumes:**
  - release_inputs
- **produces:**
  - canary_rollout_record
- **must_not_do:**
  - own_policy_authority

### DAG
- **role:** dependency graph governance.
- **status:** demoted
- **owns:**
  - dependency_graph_artifacts
- **consumes:**
  - dependency_inputs
- **produces:**
  - con_hidden_coupling_report
- **must_not_do:**
  - own_execution_authority

### EXT
- **role:** external runtime governance.
- **status:** demoted
- **owns:**
  - external_runtime_provenance_contracts
- **consumes:**
  - external_runtime_inputs
- **produces:**
  - ext_runtime_governance_bundle
- **must_not_do:**
  - own_policy_authority

### CTX
- **role:** context governance.
- **status:** active
- **owns:**
  - context_bundle_contracts
- **consumes:**
  - source_context_inputs
- **produces:**
  - context_bundle
- **must_not_do:**
  - own_closure_decisions

### EVL
- **role:** evaluation governance.
- **status:** active
- **owns:**
  - required_eval_registry
- **consumes:**
  - execution_traces
- **produces:**
  - continuous_eval_run_record
- **must_not_do:**
  - own_enforcement_actions

### OBS
- **role:** observability governance.
- **status:** active
- **owns:**
  - observability_contracts
- **consumes:**
  - runtime_signals
- **produces:**
  - observability_record
- **must_not_do:**
  - own_policy_decisions

### LIN
- **role:** lineage governance.
- **status:** active
- **owns:**
  - lineage_completeness_rules
- **consumes:**
  - artifact_lineage_inputs
- **produces:**
  - artifact_lineage
- **must_not_do:**
  - own_execution_authority

### DRT
- **role:** drift signals.
- **status:** demoted
- **owns:**
  - drift_signal_emission
- **consumes:**
  - runtime_deltas
- **produces:**
  - drift_detection_record
- **must_not_do:**
  - own_closure_decisions

### SLO
- **role:** slo governance.
- **status:** active
- **owns:**
  - slo_error_budget_artifacts
- **consumes:**
  - observability_record
- **produces:**
  - slo_ai_reliability_budget_posture
- **must_not_do:**
  - own_policy_adjudication

### DAT
- **role:** dataset governance.
- **status:** demoted
- **owns:**
  - eval_dataset_registry
- **consumes:**
  - dataset_inputs
- **produces:**
  - dat_dataset_lineage_record
- **must_not_do:**
  - own_control_decisions

### PRM
- **role:** prompt registry.
- **status:** active
- **owns:**
  - prompt_registry_authority
- **consumes:**
  - authored_prompts
- **produces:**
  - prm_prompt_registry_record
- **must_not_do:**
  - execute_runtime_work

### ROU
- **role:** route observability.
- **status:** demoted
- **owns:**
  - route_candidate_records
- **consumes:**
  - routing_inputs
- **produces:**
  - routing_decision_record
- **must_not_do:**
  - own_execution_authority

### HIT
- **role:** human override.
- **status:** demoted
- **owns:**
  - human_override_artifacts
- **consumes:**
  - operator_inputs
- **produces:**
  - override_governance_record
- **must_not_do:**
  - own_policy_authority

### CAP
- **role:** capacity governance.
- **status:** active
- **owns:**
  - cost_budget_artifacts
- **consumes:**
  - runtime_utilization_signals
- **produces:**
  - cap_budget_status_record
- **must_not_do:**
  - own_policy_authority

### SEC
- **role:** security governance.
- **status:** active
- **owns:**
  - security_guardrail_event_contracts
- **consumes:**
  - identity_permission_signals
- **produces:**
  - approval_boundary_record
- **must_not_do:**
  - own_policy_decisions

### REP
- **role:** replay governance.
- **status:** active
- **owns:**
  - replay_integrity_validation
- **consumes:**
  - execution_records
- **produces:**
  - rep_replay_integrity_record
- **must_not_do:**
  - own_policy_adjudication

### ENT
- **role:** entropy governance.
- **status:** demoted
- **owns:**
  - entropy_accumulation_detection
- **consumes:**
  - artifact_histories
- **produces:**
  - correction_mining_report
- **must_not_do:**
  - own_enforcement_authority

### CON
- **role:** contract governance.
- **status:** demoted
- **owns:**
  - interface_contract_registry
- **consumes:**
  - interface_changes
- **produces:**
  - con_interface_contract_record
- **must_not_do:**
  - own_policy_authority

### TRN
- **role:** translation support.
- **status:** demoted
- **owns:**
  - source_translation_contracts
- **consumes:**
  - source_context_inputs
- **produces:**
  - context_assembly_record
- **must_not_do:**
  - own_context_admission

### NRM
- **role:** normalization support.
- **status:** demoted
- **owns:**
  - deterministic_normalization_rules
- **consumes:**
  - translated_context_candidates
- **produces:**
  - normalized_execution_request
- **must_not_do:**
  - own_context_admission

### CMP
- **role:** comparison support.
- **status:** demoted
- **owns:**
  - comparison_run_governance
- **consumes:**
  - eval_runs
- **produces:**
  - comparison_run_record
- **must_not_do:**
  - own_eval_gate_authority

### RET
- **role:** retirement support.
- **status:** demoted
- **owns:**
  - retirement_lifecycle_rules
- **consumes:**
  - active_set_snapshot
- **produces:**
  - artifact_lifecycle_status_record
- **must_not_do:**
  - own_promotion_authority

### ABS
- **role:** abstention support.
- **status:** demoted
- **owns:**
  - abstention_taxonomy
- **consumes:**
  - judgment_candidates
- **produces:**
  - abstention_record
- **must_not_do:**
  - own_control_authority

### CRS
- **role:** consistency support.
- **status:** demoted
- **owns:**
  - cross_artifact_consistency_checks
- **consumes:**
  - artifact_bundles
- **produces:**
  - con_cross_owner_contract_compatibility_matrix
- **must_not_do:**
  - own_control_decisions

### MIG
- **role:** migration support.
- **status:** demoted
- **owns:**
  - migration_plan_contracts
- **consumes:**
  - schema_change_inputs
- **produces:**
  - contract_impact_artifact
- **must_not_do:**
  - own_policy_authority

### QRY
- **role:** query support.
- **status:** demoted
- **owns:**
  - query_index_manifest_authority
- **consumes:**
  - index_inputs
- **produces:**
  - context_assembly_record
- **must_not_do:**
  - own_context_admission

### TST
- **role:** test asset support.
- **status:** demoted
- **owns:**
  - test_asset_registry
- **consumes:**
  - test_assets
- **produces:**
  - con_shift_left_workflow_coverage_audit_result
- **must_not_do:**
  - own_eval_gate_authority

### RSK
- **role:** risk support.
- **status:** demoted
- **owns:**
  - risk_classification_taxonomy
- **consumes:**
  - eval_signals
- **produces:**
  - risk_classification_record
- **must_not_do:**
  - own_closure_authority

### EVD
- **role:** evidence support.
- **status:** demoted
- **owns:**
  - evidence_sufficiency_scoring
- **consumes:**
  - evidence_inputs
- **produces:**
  - promotion_gate_evidence_record
- **must_not_do:**
  - own_policy_authority

### SUP
- **role:** supersession support.
- **status:** demoted
- **owns:**
  - supersession_rules
- **consumes:**
  - judgment_lifecycle_inputs
- **produces:**
  - judgment_supersession_record
- **must_not_do:**
  - own_judgment_semantics

### HND
- **role:** handoff support.
- **status:** demoted
- **owns:**
  - handoff_package_contracts
- **consumes:**
  - handoff_inputs
- **produces:**
  - batch_handoff_bundle
- **must_not_do:**
  - own_execution_authority

### SYN
- **role:** synthesis support.
- **status:** demoted
- **owns:**
  - trust_signal_synthesis_rules
- **consumes:**
  - multi_signal_inputs
- **produces:**
  - calibration_summary
- **must_not_do:**
  - own_policy_authority

### GOV
- **role:** certification packaging.
- **status:** active
- **owns:**
  - certification_evidence_packaging
- **consumes:**
  - tpa_policy_decisions
- **produces:**
  - governance_gate_results
- **must_not_do:**
  - decide_policy_authority

### PRA
- **role:** promotion readiness.
- **status:** active
- **owns:**
  - promotion_readiness_artifacts
- **consumes:**
  - closure_decision_artifact
- **produces:**
  - promotion_gate_decision_artifact
- **must_not_do:**
  - decide_policy_authority

### MET
- **role:** measurement and observation capability (non-owning).
- **status:** active
- **authority:** none
- **owns:**
  - measurement_observations
  - signal_compression
  - readiness_evidence_inputs
  - owner_handoff_inputs
  - improvement_inputs
- **consumes:**
  - evl_evaluation_inputs
  - lin_lineage_inputs
  - rep_replay_inputs
  - obs_observability_inputs
  - slo_error_budget_inputs
  - tpa_trust_inputs
  - cde_control_inputs
  - sel_enforcement_inputs
- **produces:**
  - candidate_closure_ledger_record
  - outcome_attribution_record
  - recommendation_accuracy_record
  - calibration_drift_record
  - signal_confidence_record
  - cross_run_consistency_record
  - met_error_budget_observation_record
  - next_best_slice_recommendation_record
  - counterfactual_reconstruction_record
  - recurring_failure_cluster_record
  - signal_integrity_check_record
- **must_not_do:**
  - own_decision_authority
  - own_approval_authority
  - own_enforcement_authority
  - own_certification_authority
  - own_promotion_authority
  - own_execution_authority
  - own_admission_authority
  - emit_authority_outcomes

### HOP
- **role:** harness optimization substrate.
- **status:** active
- **owns:**
  - harness_candidate_storage
  - harness_run_records
  - harness_eval_orchestration
  - harness_frontier_tracking
  - harness_eval_set_curation
- **consumes:**
  - hop_harness_eval_case
  - transcript_input
- **produces:**
  - hop_harness_candidate
  - hop_harness_run
  - hop_harness_score
  - hop_harness_trace
  - hop_harness_frontier
  - hop_harness_failure_hypothesis
  - hop_harness_faq_output
- **must_not_do:**
  - own_promotion_decisions
  - own_closure_authority
  - own_enforcement_authority
  - bypass_eval_system
  - bypass_schema_validation
  - emit_free_form_outputs

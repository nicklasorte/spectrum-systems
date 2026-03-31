# Autonomous Execution Loop (Closed-Loop Slice)

This slice extends the deterministic fail-closed control-plane from foundation seams to live write-back behavior, including review ingestion and fix-loop re-entry.

## Core boundaries
- Planning artifacts are separate from execution artifacts.
- Review artifacts are evidence, not control decisions.
- Roadmap planning may include many future steps, but roadmap eligibility only reports which steps are ready now; it does not authorize execution.
- Control remains the only layer that can select a single next step for execution.
- PQX remains execution-only and one-step-at-a-time; no multi-step autonomy is authorized by roadmap or eligibility artifacts.
- GOV-10 done certification is the required final gate.
- Missing required artifact, invalid artifact, or failed handoff blocks progression.

## Cycle Manifest as Source of Truth
- `cycle_manifest` is the authoritative control artifact for loop state; if a field is not persisted in the manifest, it is not part of loop state.
- The manifest must link roadmap, eligibility, and decision artifacts through explicit paths:
  - `roadmap_artifact_path`
  - `roadmap_eligibility_artifact_path`
  - `next_step_decision_artifact_path`
- Decision trace state is persisted directly in the manifest (`selected_step_id`, `selected_step_status`, `decision_summary`, `decision_blocked`, `decision_block_reason`, eligibility snapshots).
- PQX execution is authorization-bound: execution requests are valid only when `step_id == selected_step_id` from the manifest.
- Replay is artifact-driven and deterministic: manifest + referenced artifacts are sufficient to reconstruct why progression advanced or blocked.

## Implemented components
- `cycle_manifest` contract and example with live handoff/write-back tracking fields.
- `spectrum_systems/orchestration/cycle_runner.py` deterministic state progression with execution + certification write-back.
- `spectrum_systems/orchestration/cycle_runner.py` deterministic review ingestion, fix-roadmap auto-generation, PQX re-entry, and certification state progression.
- `spectrum_systems/orchestration/pqx_handoff_adapter.py` live PQX adapter around `run_pqx_slice`.
- `spectrum_systems/fix_engine/generate_fix_roadmap.py` deterministic grouping and output of machine-readable + markdown fix roadmaps.
- Live seam integrations:
  - PQX execution handoff (`spectrum_systems.modules.runtime.pqx_slice_runner.run_pqx_slice`)
  - implementation review ingestion (`implementation_review_artifact` validation)
  - fix-roadmap generation (`fix_roadmap_artifact` write-back)
  - PQX fix re-entry handoff (`spectrum_systems.orchestration.pqx_handoff_adapter.handoff_to_pqx`)
  - GOV-10 done certification handoff (`spectrum_systems.modules.governance.done_certification.run_done_certification`)
- Integration tests covering happy path, blocked paths, and deterministic replay behavior.

## Strategy/source authority enforcement in-loop (grouped PQX slice)
- `cycle_manifest` governed path now requires explicit authority fields at cycle entry:
  - `strategy_authority` (must resolve to canonical strategy path `docs/architecture/system_strategy.md`)
  - non-empty `source_authorities` (bounded source references declared in `docs/architecture/system_source_index.md`)
- `roadmap_review_artifact` now carries machine-readable `governance_provenance` with:
  - strategy authority used
  - source authorities used
  - invariant checks applied
  - drift findings
- `cycle_runner` hard gates progression (fail closed) when governed inputs are missing or invalid:
  - missing/invalid strategy authority, missing source authorities, missing authority files, duplicate source refs, or undeclared source refs
  - missing/mismatched roadmap review provenance linkage
  - failed invariant checks or blocking drift findings in roadmap provenance
- Downstream traceability is preserved across the deterministic artifact chain:
  - `cycle_manifest` authority declarations
  - `roadmap_review_artifact` provenance linkage
  - progression decision outputs/blocked reasons produced by `cycle_runner`.

## Closed-loop transition behavior
Happy path progression for this slice:
`execution_ready -> execution_complete_unreviewed -> implementation_reviews_complete -> fix_roadmap_ready -> fixes_in_progress -> fixes_complete_unreviewed -> certification_pending -> certified_done`

Blocked terminal behavior:
- missing/invalid PQX request or output artifacts
- missing/invalid roadmap or implementation review artifacts
- fix-roadmap generation failure or invalid fix-roadmap artifact
- missing/invalid fix execution report write-back from PQX re-entry
- invalid execution report contract
- missing/invalid/failing done certification result

`blocked` is terminal until an operator repairs inputs and reruns the cycle.


## Cycle observability/status extension (grouped PQX slice)
- Added deterministic read-only status builder: `spectrum_systems/orchestration/cycle_observability.py`.
- Added contract-backed observability artifacts:
  - `cycle_status_artifact` (single-cycle machine-readable status + markdown summary)
  - `cycle_backlog_snapshot` (multi-cycle queue/backlog rollup + deterministic metrics)
- Status surfaces include: `cycle_id`, `current_state`, `next_action`, blocked reason summary, artifact refs, and `last_updated`.
- Blocked reasons are normalized into stable deterministic categories: `missing_required_artifact`, `invalid_artifact_contract`, `pqx_execution_failure`, `review_missing`, `review_invalid`, `fix_generation_failure`, `certification_missing`, `certification_failed`, `other`.
- Queue/backlog views are derived from manifests only and include active/blocked/certification-pending/awaiting-review/awaiting-PQX cohorts.
- Metrics are artifact-derived only (no hidden state/cache): count by state, blocked-by-reason, average execution seconds when timestamps are complete, critical/blocker finding counts from review artifacts, and certification pass/fail counts.
- Fail-closed behavior is preserved: blocked manifests without details and incomplete phase timing metadata raise deterministic errors instead of producing healthy-looking status.

## Judgment + precedent layer (artifact-first extension)

This grouped slice adds a deterministic judgment seam for `artifact_release_readiness` without collapsing role boundaries.

### New judgment artifacts
- `judgment_policy`: versioned policy artifact with deterministic selection keys (`judgment_type`, `scope`, `environment`) and status (`draft/canary/active/deprecated`).
- `judgment_record`: rationale-bearing judgment result with claims, evidence refs, rule application, alternatives, uncertainties, conditions for decision change, and precedent trace.
- `judgment_application_record`: captures policy matching set, selected policy, conflict signals, deviation notes, and final outcome.
- `judgment_eval_result`: deterministic multi-eval artifact containing evidence coverage, policy alignment, replay consistency, and thin calibration/drift scaffolding.

### Policy registry behavior
- Registry input is explicit `judgment_policy_paths` in `cycle_manifest`.
- Policies are loaded from repo artifacts only (no hidden state/cache).
- Selection is deterministic:
  1. filter by `judgment_type + scope + environment`
  2. keep `active/canary`
  3. order by status (`active` before `canary`), semantic version descending, `artifact_id` ascending.

### Precedent retrieval behavior
- Retrieval method: deterministic `exact-field-overlap`.
- Inputs are bounded by policy-declared `query_fields`; missing required retrieval inputs fail closed.
- Record includes `method_id`, `method_version`, `threshold`, `top_k`, `similarity_basis`, and scored precedent refs.
- Sorting is deterministic by score (desc) then record ref (asc).

### Control gating behavior
- `roadmap_approved -> execution_ready` can require `artifact_release_readiness` judgment.
- If required judgment artifacts are missing or invalid: cycle blocks.
- If required judgment eval types (`evidence_coverage`, `policy_alignment`, `replay_consistency`) are missing from `judgment_eval_result`: cycle blocks.
- If any required judgment eval fails: cycle blocks.
- If judgment outcome is `block`: cycle blocks.
- If outcome is `revise`: cycle blocks pending explicit remediation (no silent promotion).
- Only `approve` allows normal progression when other hard gates are satisfied.

### Judgment evaluation behavior (grouped PQX slice)
- Evidence coverage: deterministic scoring over `claims_considered` material claims and explicit `supported_by_evidence_ids` linkage.
- Policy alignment: compares `judgment_record.selected_outcome` with `judgment_application_record.final_outcome`; silent divergence fails closed unless explicit `policy_deviation:` note is present.
- Replay consistency: records a deterministic fingerprint hash of control-relevant judgment fields and compares against replay reference when provided.

### Calibration/drift scaffolding now present
- Outcome labeling seam via `calibration_scaffolding.outcome_label_input_path`.
- Longitudinal calibration placeholder path via `calibration_scaffolding.longitudinal_artifact_path`.
- Drift signal scaffold via `drift_signal_scaffolding` metadata and `judgment_outcome_drift_signal` eval result.

### Deferred for later calibration/drift phases
- Population-level calibration metric computation and threshold governance.
- Longitudinal calibration runners consuming human-labeled outcomes.
- Drift alerting and control integration using aggregated judgment outcome distributions.

## Judgment learning extension (grouped PQX slice)

This extension hardens judgment-eval scaffolding into deterministic governed learning artifacts without introducing a parallel control plane.

### Replay reference sourcing
- Replay consistency now supports external replay reference artifacts in addition to the existing self-consistency path.
- Deterministic comparison checks expected outcome vs actual `judgment_record.selected_outcome` and (when present) reference fingerprint hash vs current fingerprint hash.
- Replay eval details and `judgment_eval_result.replay_reference` now explicitly record:
  - `source`
  - `comparison_result`
  - `mismatch_reason`
  - `expected_outcome`
  - `actual_outcome`
- If policy sets `judgment_eval_requirements.replay_consistency.require_reference_artifact=true` and no replay reference is provided, replay consistency fails closed.

### Outcome label ingestion
- Added governed `judgment_outcome_label` artifact for post-judgment ground truth ingestion.
- Required fields: `judgment_id`, `observed_outcome`, `expected_outcome`, `correctness`, `source`, `timestamp`.
- Ingestion is schema-validated and fail-closed; invalid or partial labels are rejected.

### Longitudinal calibration
- Added deterministic `judgment_calibration_result` artifact generation.
- Grouping dimensions: `judgment_type`, `policy_version`, `environment`.
- Metrics:
  - `accuracy = correct_count / sample_size`
  - ECE-style calibration error across fixed 0.1 confidence bins
  - `calibration_delta = mean_confidence - accuracy`
  - confidence classification (`overconfident` / `underconfident` / `well_calibrated`)
- Formulas are written directly into the artifact for inspectability.

### Drift signal computation
- Added deterministic `judgment_drift_signal` artifact generation from baseline/current calibration artifacts.
- Computes deltas for:
  - approval rate
  - block rate
  - error rate
  - calibration ECE
- Threshold-based boolean drift triggers are explicit in artifact payload.

## Judgment learning → control enforcement integration (grouped PQX slice)

This grouped slice wires learning artifacts directly into deterministic control decisions without adding a parallel control plane.

### New governed artifacts
- `judgment_error_budget_status`: deterministic budget status grouped by `judgment_type`, `policy_version`, and `environment`.
  - Tracks `wrong_allow_rate`, `wrong_block_rate`, and `override_rate`.
  - Computes `budget_remaining` and `burn_rate` per metric.
  - Fails closed when labels or eval coverage are missing.
- `judgment_control_escalation_record`: emitted for every learning-signal control decision.
  - Includes `decision` (`allow|warn|freeze|block`), triggering signal summary, threshold snapshot, rationale, and trace linkage.

### Policy-governed thresholding
- `judgment_policy.learning_control_policy` now carries explicit versioned thresholds:
  - drift warning + critical deltas
  - error-budget limit caps
  - calibration warn/freeze bands
  - override-rate warn threshold
- Drift threshold evaluation maps each group deterministically to:
  - `no_drift`
  - `warning_drift`
  - `critical_drift`

### Control decision mapping (deterministic + fail-closed)
- `block` if:
  - any required eval fails
  - error budget is exhausted or invalid
  - critical drift is detected
  - required learning artifacts are missing/invalid
- `freeze` if:
  - warning drift threshold is exceeded
  - calibration error exceeds freeze band
- `warn` if:
  - override rate is rising
  - calibration error is in warn band
  - non-critical budget warning is present
- `allow` only when evals pass, drift is clear, calibration is healthy, and budget is healthy.

## Judgment escalation enforcement wiring (grouped PQX slice)

`judgment_control_escalation_record` is now the authoritative enforcement input for the judgment learning-control seam.

### Deterministic decision -> action mapping
- `allow` -> `promote_or_continue` action (never silent pass-through).
- `warn` -> `continue_with_warning` action; warning-remediation hook is emitted when warning state is policy-relevant (for example non-healthy calibration warning bands).
- `freeze` -> `freeze_pipeline_or_freeze_scope` action; progression remains frozen and requires operator remediation artifacts.
- `block` -> `block_artifact_or_block_progression` action; progression is prevented and requires governed override/remediation artifacts.

### New downstream governed artifacts
- `judgment_enforcement_action_record`: records deterministic execution intent and policy refs used for enforcement.
- `judgment_enforcement_outcome_record`: records enforcement outcome and progression status (`allowed`, `allowed_with_warning`, `frozen`, `prevented`).
- `judgment_operator_remediation_record`: explicit human-required remediation hook for freeze/block and policy-required warning paths.

### Fail-closed integration rules
- Missing escalation artifact -> block.
- Missing enforcement action artifact -> block.
- Missing enforcement outcome artifact on required paths -> block.
- Missing required remediation artifact -> block.
- Freeze/block states remain blocked until governed remediation status transitions through explicit artifact updates.

This preserves end-to-end traceability: learning signal -> control escalation decision -> enforcement action -> enforcement outcome -> operator remediation (when required).

## Decision → remediation routing → fix-plan bridge (control + recovery)

- `next_step_decision` now emits explicit remediation requirement metadata on blocking outcomes:
  - `remediation_required`
  - `remediation_class`
  - `blocking_reason_category`
- Blocking decisions are routed through governed `drift_remediation_policy` (not ad hoc branching).
- The orchestration seam now materializes two deterministic child artifacts before progression halts:
  - `drift_remediation_artifact`
  - `fix_plan_artifact`
- `cycle_manifest` persists references to both artifacts, and progression remains blocked until a later slice completes governed remediation execution.
- This slice stops at fix-plan generation; it does **not** execute fixes, approve fixes, or perform replay-after-repair.

## Remediation closure/reinstatement readiness observability extension (grouped PQX slice)

This slice adds deterministic, read-only readiness artifacts to explain closure and reinstatement eligibility without changing enforcement authority.

### New governed observability artifacts
- `judgment_remediation_readiness_status`
  - Answers: “Is this remediation ready to close? If not, why?”
  - Includes lifecycle state, required evidence refs, evidence present/missing, required thresholds, thresholds satisfied/not satisfied, closure eligibility, normalized blockers, and trace linkage.
- `judgment_reinstatement_readiness_status`
  - Answers: “Can this frozen/blocked path resume? If not, why?”
  - Includes closure/reinstatement artifact present+valid signals, required gate satisfaction, reinstatement eligibility, resulting eligible state (`unblock`/`unfreeze`/`continue`), normalized blockers, and trace linkage.

### Deterministic readiness evaluation
- `build_remediation_readiness_status(...)` and `build_reinstatement_readiness_status(...)` compute readiness strictly from supplied artifacts and explicit inputs.
- No hidden state or mutable cache is used.
- Missing required evidence, missing closure artifact, or missing reinstatement artifact fails closed (`eligible=false`).
- Normalized blockers include:
  - `missing_required_evidence`
  - `missing_eval_result`
  - `threshold_not_met`
  - `missing_closure_artifact`
  - `missing_reinstatement_artifact`

### Backlog/queue visibility extension
- `cycle_backlog_snapshot` now includes remediation/reinstatement cohorts:
  - open remediations
  - remediations ready for closure
  - remediations blocked on missing evidence
  - remediations pending review
  - reinstatement-ready items
  - frozen/blocked items with unresolved remediation
- Cohorts are derived from governed artifacts only and never mutate control state.

### Operator/control support
- Operators can identify precise blockers before attempting closure/reinstatement.
- Automation can inspect explicit readiness/blocked reasons instead of inferring from lifecycle transitions.
- Authority boundaries remain unchanged: these artifacts report readiness only and do not trigger enforcement or state transitions.

## Remediation closure + progression reinstatement extension (grouped PQX slice)

This extension keeps the existing control/enforcement seam and hardens remediation handling without introducing a parallel remediation plane.

### Deterministic remediation lifecycle
- `judgment_operator_remediation_record` now uses explicit lifecycle states:
  - `open`
  - `in_progress`
  - `evidence_submitted`
  - `pending_review`
  - `approved_for_closure`
  - `closed`
  - `rejected`
- Transitions are explicit and validated in `transition_judgment_remediation_status`; invalid jumps fail closed (for example `open -> closed`).
- Transition events are stored in deterministic `status_history`; no silent status mutation is allowed.

### Closure artifact and replay-safe checks
- Added `judgment_remediation_closure_record` as the only governed closure mechanism for freeze/block/policy-required warn remediation paths.
- Closure records bind to source remediation/escalation/action/outcome ids, evidence refs reviewed, policy version, and deterministic replay-safe checks.
- Replay-safe checks verify required evidence refs, enforcement-outcome linkage, threshold satisfaction, source-condition resolution, and explicit policy-version binding.
- If closure checks cannot be reproduced from artifacts, progression remains blocked/frozen.

### Reinstatement artifact and resumed progression governance
- Added `judgment_progression_reinstatement_record` as a separate authorization artifact from closure.
- Closure means remediation is sufficient; reinstatement means progression is allowed to resume.
- Freeze/block (and policy-required warn) paths require valid reinstatement artifacts before progression can resume.
- Reinstatement types are explicit (`unblock`, `unfreeze`, `warning_acknowledged_continue`) and are decision-bound.

### Fail-closed integration behavior
- Freeze/block states remain active until remediation is `closed`, closure is approved, and required reinstatement is present and valid.
- Rejected/insufficient closure evidence keeps progression blocked/frozen.
- Warn paths with required remediation cannot silently continue until closure + warning reinstatement are valid.
- Traceability remains artifact-first: escalation -> action -> outcome -> remediation -> closure -> reinstatement.


## Judgment policy lifecycle governance extension (grouped PQX slice)

This slice extends the existing judgment policy seam with explicit lifecycle + rollout artifacts, governed canary cohorting, promotion gates, and explicit rollback/revoke behavior.

### New governed lifecycle artifacts
- `judgment_policy_rollout_record`
  - Required for canary activation.
  - Defines deterministic cohort (`environment`, `trace_bucket`, or `explicit_trace_ids`) and expected promotion gates.
  - Tracks rollout mode (`canary`, `staged`, `full`) and current rollout status.
- `judgment_policy_lifecycle_record`
  - Required for every policy status transition.
  - Captures `from_version -> to_version`, lifecycle action (`create_draft`, `enter_canary`, `promote_active`, `deprecate`, `rollback`, `revoke`), source reasons/triggering signals, gate evaluations, resulting status, actor, and trace linkage.

### Lifecycle states and status semantics
- `draft`: not selectable for execution.
- `canary`: selectable only for traffic inside the rollout cohort declared in an active `judgment_policy_rollout_record`.
- `active`: globally selectable when matching type/scope/environment.
- `deprecated`: retained for audit history but not newly selected.
- `revoked`: unusable; selection is blocked immediately and deterministically.

### Canary cohorting rules
- Cohorts are artifact-declared and deterministic (no runtime randomness):
  - environment set membership
  - trace-id hash bucket membership (`sha256(trace_id) % modulo in buckets`)
  - explicit trace-id allowlist
- Missing rollout artifact or unsupported cohort definition fails closed (canary policy is not selected).

### Promotion gate requirements (canary -> active)
Promotion requires all governed inputs and healthy gate outcomes:
- `judgment_eval_result` present and all required eval checks passing
- `judgment_drift_signal` present and no detected drift across governed groups
- `judgment_error_budget_status` present with `status=healthy`
- remediation readiness shows no unresolved critical closure blockers for affected policy version
- required readiness/control checks explicitly true

If any required signal is missing, promotion fails closed.

### Rollback and revoke semantics
- Rollback is explicit: current version transitions to a provided prior active target version; target must be supplied and valid.
- Revoke is explicit: target version transitions to `revoked`, and selection logic blocks the version from future use.
- Both rollback and revoke emit `judgment_policy_lifecycle_record`; no silent fallback is allowed.

### Policy registry integration behavior
- Global selection remains deterministic:
  1. type/scope/environment filter
  2. status and lifecycle-governance filter (`active` global, `canary` cohort-bound, `deprecated/revoked` excluded)
  3. deterministic tie-break (`status rank`, semantic version desc, `artifact_id` asc)
- When lifecycle/rollout artifacts are supplied to the governed selection path, missing lifecycle evidence for candidate versions fails closed.


### Mandatory governed lifecycle enforcement (hardening)
- Governed cycle/runtime judgment selection now **requires** `judgment_policy_lifecycle_record` evidence for selectable policy versions.
- Canary selection on governed paths now **requires** both lifecycle evidence and active `judgment_policy_rollout_record` cohort evidence.
- Missing lifecycle evidence or missing canary rollout evidence fails closed and blocks cycle progression (no optional bypass on governed runtime/control paths).
- Governed cycle manifests must provide `judgment_policy_lifecycle_paths` and `judgment_policy_rollout_paths`; lifecycle/rollout artifacts are validated before policy selection.
- Downstream linkage is preserved from policy selection through escalation/enforcement artifacts: `selected_policy_id`, `selected_policy_version`, `policy_lifecycle_status`, and `policy_rollout_id` (or `none` when non-canary).

## Contract-impact pre-execution gate (G13)
- PQX slice execution now supports a governed `contract_impact_artifact` preflight.
- The artifact may be supplied directly or generated from changed contract paths before execution.
- Execution blocks fail-closed when compatibility is `breaking` or `indeterminate`, when `blocking=true`, or when `safe_to_execute=false`.
- This gate is pre-execution trust enforcement and does not replace contract/runtime tests.

# Autonomous Execution Loop (Closed-Loop Slice)

This slice extends the deterministic fail-closed control-plane from foundation seams to live write-back behavior, including review ingestion and fix-loop re-entry.

## Core boundaries
- Planning artifacts are separate from execution artifacts.
- Review artifacts are evidence, not control decisions.
- PQX is execution-only; control decides next actions.
- GOV-10 done certification is the required final gate.
- Missing required artifact, invalid artifact, or failed handoff blocks progression.

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

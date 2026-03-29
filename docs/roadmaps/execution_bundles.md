# Spectrum Systems — Execution Bundles

## INTENT
Create a deterministic, fail-closed bundling model that turns the active roadmap authority into a PQX-executable sequence of **24 ordered steps** (target 20–30), with strict dependency enforcement, review checkpoints, fix re-entry, and replayable state.

This bundle plan is authoritative for multi-slice execution orchestration design and is aligned to:
- active roadmap authority and compatibility bridge rules,
- step-contract completeness requirements,
- current PQX runtime/state behavior,
- source-derived reliability and governance obligations (including explicit source-gap handling).

## EXECUTION MODEL
1. **Unit of execution = step.**
   - Each step MUST satisfy `docs/roadmap/roadmap_step_contract.md` required fields before scheduling.
   - Step IDs in this plan: `B3-01`…`B3-24`.
2. **Unit of advancement = bundle.**
   - Bundles contain 3–7 steps each.
   - Steps run sequentially inside bundle; no parallel execution.
3. **Artifact-first chaining.**
   - Every step emits schema-bound artifacts; next step consumes prior artifacts only (no implicit memory).
4. **Fail-closed behavior.**
   - Any step failure blocks bundle completion and emits `block_record`.
   - Bundle completion artifact (`bundle_execution_record`) is emitted only when all steps in bundle pass and required reviews pass.
5. **Deterministic replay.**
   - State + artifacts persist per step and per bundle.
   - Replay starts from last completed step or fix insertion point; duplicate completion is rejected.

## BUNDLE TABLE

| Bundle ID | Steps | What It Builds | Entry Conditions | Exit Conditions | Artifacts | Review Required | Risks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BUNDLE-01 | B3-01..B3-04 | Authority lock + step-contract gate + baseline state model | Active authority docs resolve cleanly; inventory exists | Authority bridge validated; 24-step machine list generated; state initialized | `authority_resolution_record`, `step_contract_lint_report`, `execution_plan_artifact`, `pqx_bundle_state` | Architecture + contract validation | Authority/mirror mismatch blocks all execution |
| BUNDLE-02 | B3-05..B3-08 | Dominant single-slice governed baseline (PQX-BASE hardening) | BUNDLE-01 complete | Single-slice golden path complete with fail-closed evidence | `slice_execution_record`, `control_decision_artifact`, `enforcement_record`, `single_slice_certification_record` | Architecture + failure-mode audit | False-positive single-slice success without full evidence chain |
| BUNDLE-03 | B3-09..B3-12 | Two-slice sequential governance (PQX-SEQ-2) with resume/replay guarantees | BUNDLE-02 complete | Two sequential slices complete or explicit fail block with replay token continuity | `sequence_state_snapshot`, `slice_transition_record`, `replay_resume_record`, `bundle_execution_record` | Contract validation + failure-mode audit | Continuity drift (trace/run IDs) and partial-sequence ambiguity |
| BUNDLE-04 | B3-13..B3-16 | Three-slice trust hardening + review routing convergence (PQX-SEQ-3) | BUNDLE-03 complete | Three slices pass with deterministic review gating + reentry semantics | `review_trigger_record`, `review_artifact`, `findings_register`, `reentry_decision_record` | Architecture + contract validation + failure-mode audit | Review bypass or malformed findings-to-action conversion |
| BUNDLE-05 | B3-17..B3-20 | 5–10 slice control for budgets, certification, and audit closure (PQX-SEQ-5-10 foundation) | BUNDLE-04 complete | Controlled 5-slice run succeeds with budget/certification/audit gates enforced | `sequence_budget_decision`, `multi_slice_certification_record`, `audit_bundle_record`, `promotion_gate_record` | Architecture + failure-mode audit | Batch-scale control loop instability; premature promotion |
| BUNDLE-06 | B3-21..B3-24 | Rack-and-stack fix loop + production readiness closure | BUNDLE-05 complete OR blocked with findings | Findings converted to fix steps, executed, and closure-certified; readiness decision emitted | `rack_stack_record`, `fix_bundle_plan`, `fix_execution_record`, `readiness_decision_record` | Architecture + contract validation | Infinite fix churn; duplicate or out-of-order fix replay |

## BUNDLE DETAILS

### BUNDLE-01
- Steps:
  - `B3-01` Resolve roadmap authority bridge (`docs/roadmaps/roadmap_authority.md`) and fail on ambiguity.
  - `B3-02` Validate compatibility mirror alignment and parseability against step contract requirements.
  - `B3-03` Generate machine step inventory (24 ordered executable steps + dependencies).
  - `B3-04` Initialize persistent `pqx_bundle_state` with deterministic run identity.
- Flow:
  - Authority resolve → mirror verify → step inventory compile → state write.
- Artifacts:
  - `authority_resolution_record`, `compatibility_integrity_record`, `execution_plan_artifact`, `pqx_bundle_state`.
- Failure Handling:
  - Any bridge mismatch emits `block_record{block_type:AUTHORITY_MISMATCH}` and halts.
- Review:
  - Mandatory architecture review (authority/control loop integrity) + contract validation review.

### BUNDLE-02
- Steps:
  - `B3-05` Execute single-slice admission + context validation (eval-first precondition).
  - `B3-06` Execute governed slice and emit normalized execution result.
  - `B3-07` Run control decision + enforcement decision emission.
  - `B3-08` Require done certification artifact for slice completion.
- Flow:
  - Admission artifact → execution artifact → control/enforcement artifacts → certification artifact.
- Artifacts:
  - `context_admission_record`, `slice_execution_record`, `loop_control_decision`, `done_certification_record`.
- Failure Handling:
  - Missing certification forces `status=failed` even if execution result is success.
- Review:
  - Post-bundle architecture review + targeted failure-mode audit (silent-success prevention).

### BUNDLE-03
- Steps:
  - `B3-09` Start deterministic sequence run (2 slices) with persisted state artifact.
  - `B3-10` Enforce parent-child continuity (`queue_run_id`, `run_id`, `trace_id`, parent ref).
  - `B3-11` Validate replay/resume token integrity and deterministic reload parity.
  - `B3-12` Emit bundle completion or block artifact for two-slice run.
- Flow:
  - Sequence init → continuity checks → replay checks → completion/block emission.
- Artifacts:
  - `prompt_queue_sequence_run`, `sequence_continuity_report`, `replay_integrity_record`, `bundle_execution_record`.
- Failure Handling:
  - Any continuity mismatch emits `block_record{block_type:CONTINUITY_MISMATCH}`.
- Review:
  - Mandatory contract validation review; failure-mode audit required.

### BUNDLE-04
- Steps:
  - `B3-13` Execute third slice under same deterministic lineage and state invariants.
  - `B3-14` Trigger mandatory review checkpoints after bundle and optional high-risk step review.
  - `B3-15` Validate `review_artifact` schema and findings severity classification.
  - `B3-16` Convert accepted findings into reentry-ready patch directives.
- Flow:
  - Slice 3 run → review trigger → findings validate → reentry conversion.
- Artifacts:
  - `three_slice_execution_record`, `review_artifact`, `findings_register`, `patch_directive_record`.
- Failure Handling:
  - Missing review artifact after trigger emits `block_record{block_type:REVIEW_MISSING}`.
- Review:
  - Full triad required: architecture review, contract validation, failure-mode audit.

### BUNDLE-05
- Steps:
  - `B3-17` Execute bounded 5-slice run with explicit sequence budget and stop conditions.
  - `B3-18` Enforce per-slice and aggregate policy gates (eval, control, enforcement all required).
  - `B3-19` Build certification + audit closure artifacts across all executed slices.
  - `B3-20` Run promotion gate decision (fail closed on missing/failed cert evidence).
- Flow:
  - Budgeted sequence execute → gate checks → trust artifact packaging → promotion decision.
- Artifacts:
  - `sequence_budget_record`, `policy_gate_matrix`, `multi_slice_certification_record`, `audit_bundle_record`, `promotion_gate_record`.
- Failure Handling:
  - Promotion blocked unless all gates green and all artifacts schema-valid.
- Review:
  - Post-bundle architecture review + failure-mode audit mandatory.

### BUNDLE-06
- Steps:
  - `B3-21` Rack-and-stack all open findings and classify (`critical|high|medium`).
  - `B3-22` Generate fix insertion plan (new roadmap steps vs patch steps) with deterministic insertion points.
  - `B3-23` Execute fix bundle and re-run affected bundle validations only.
  - `B3-24` Emit readiness decision for 5–10 sequential slices and freeze execution snapshot.
- Flow:
  - Findings aggregate → prioritize/insert → fix execute → readiness certify.
- Artifacts:
  - `rack_stack_record`, `fix_bundle_plan`, `fix_execution_record`, `sequential_readiness_decision`.
- Failure Handling:
  - If critical findings remain open, emit `block_record{block_type:OPEN_CRITICAL_FINDINGS}`.
- Review:
  - Mandatory architecture + contract validation before final readiness decision.

## REVIEW SYSTEM
- **Trigger points**
  - Required: after every bundle (`BUNDLE-01`..`BUNDLE-06`).
  - Optional-but-enforced when configured: after high-risk steps (`B3-08`, `B3-11`, `B3-15`, `B3-20`, `B3-24`).
- **Review types**
  - Architecture review (Claude-led; control-loop integrity, dependency soundness).
  - Contract validation review (Codex-led; schema and step-contract conformance).
  - Failure-mode audit (joint; fail-closed and replay guarantees).
- **Required outputs**
  - `review_artifact` (schema-bound),
  - `findings` list (id, severity, blocked_scope, evidence refs),
  - `required_fixes` list (actionable, dependency-tagged).
- **Bypass prevention**
  - Bundle status cannot become `complete` without required review artifacts.
  - Review hash must match bundle artifact hash set; mismatch blocks advancement.

## FIX INSERTION MODEL
1. **Finding conversion rules**
   - `critical`: always inserts **new fix bundle step(s)** before next unresolved bundle.
   - `high`: inserts patch step into current stream; can batch if same seam.
   - `medium`: queued into nearest compatible bundle tail unless it affects contracts, then immediate.
2. **Insertion location rule**
   - Fixes re-enter at the earliest bundle that owns the failing seam.
   - If seam spans bundles, re-enter at first downstream dependency consumer.
3. **Step generation rule**
   - New steps use IDs `B3-FIX-XX` and include full step-contract fields.
   - Fix steps are append-only; original historical step order remains immutable.
4. **Closure rule**
   - Every finding must link to either `deferred_with_rationale` or `fixed_by_step_id`.
   - Open critical/high findings block `B3-24` readiness issuance.

## PQX EXECUTION MODEL
- **Bundle selection**
  - Determine next bundle by scanning `completed_bundles` in persistent state and selecting first incomplete bundle with satisfied dependencies.
- **Dependency enforcement**
  - Step scheduler validates direct dependencies only; transitive closure inferred from prior validations.
  - Missing dependency, incomplete dependency, or unknown step ID yields immediate block.
- **Runtime compatibility mapping**
  - `pqx_backbone.resolve_roadmap_authority` equivalent gate is first preflight for `B3-01`.
  - `pqx_backbone.resolve_executable_row` semantics map to step selection and dependency blocks.
  - `runtime/pqx_sequence_runner.execute_sequence_run` semantics map to B3-09..B3-20 continuity/replay execution.
- **Next bundle choice**
  - If current bundle has any failed step or required review missing: emit `block_record`, set `active_bundle_status=blocked`, and require fix insertion before advancing.
  - Else mark bundle complete and move to next bundle.

## STATE MODEL
Persisted artifact: `pqx_bundle_state` (JSON, deterministic ordering).

Required fields:
- `run_id`, `queue_run_id`, `trace_id`
- `active_bundle_id`
- `completed_steps` (ordered list)
- `completed_bundles` (ordered list)
- `failed_steps` (list with error + block_type)
- `pending_fixes` (finding_id → planned_step_id)
- `step_artifact_index` (step_id → artifact refs + hashes)
- `review_index` (bundle_id/step_id → review_artifact ref)
- `resume_token`
- `state_version`

Determinism constraints:
- State reload must be byte-stable after persist/reload roundtrip.
- Completed steps cannot be re-executed unless `rerun_completed=true` is explicitly set and audited.
- Artifact hashes and ordering are immutable once bundle is complete.

## FAILURE MODES PREVENTED
- **Partial bundle execution:** prevented by bundle-level completion gate requiring all steps + reviews.
- **Skipped dependencies:** prevented by pre-step dependency validation and immediate dependency block records.
- **Silent failures:** prevented by mandatory block record emission and explicit failed step state.
- **Review bypass:** prevented by required `review_artifact` presence/hash matching for completion.
- **Infinite loops:** prevented by fix-step append-only model, max retry policy, and unresolved-critical hard block.
- **Duplicate step execution:** prevented by completed-step immutability with explicit audited override only.

## GUARANTEES
- 24-step sequential execution path (within required 20–30 range) with deterministic dependencies.
- Bundle-scoped replayable execution and review-integrated fail-closed advancement.
- Eval-first, artifact-first control-loop integrity enforced at every bundle gate.
- Certification readiness anchored to explicit multi-slice evidence and blocked on unresolved critical findings.
- Source-gap-aware governance: missing raw source files cannot be silently ignored; structured source artifacts remain explicit bounds.

## NEXT RISKS
- Structured source artifacts are placeholders due to missing raw PDFs; semantic design fidelity risk remains until source recovery.
- Legacy compatibility mirror drift can still block execution if updates are not mirrored consistently.
- High fix volume in BUNDLE-06 may reduce throughput; enforce strict prioritization and seam ownership to avoid churn.

## EXECUTABLE BUNDLE TABLE

| Bundle ID | Ordered Step IDs | Depends On |
| --- | --- | --- |
| BUNDLE-PQX-CORE | AI-01, AI-02, TRUST-01, SRE-03, GOV-10 | - |


## REVIEW CHECKPOINT TABLE

| Checkpoint ID | Bundle ID | Review Type | Scope | Step ID | Required | Blocking Before Continue |
| --- | --- | --- | --- | --- | --- | --- |
| BUNDLE-PQX-CORE:post_bundle_review | BUNDLE-PQX-CORE | post_bundle_review | bundle | - | true | true |

### B6 operator notes

- `run_pqx_bundle.py run` stops with blocked status when this checkpoint is unresolved.
- `run_pqx_bundle.py ingest-findings` attaches and validates `pqx_review_result`, then writes pending fixes into `pqx_bundle_state`.
- Resume is deterministic: once checkpoint is satisfied and blocking findings are resolved, rerun resumes from persisted `resume_position`.

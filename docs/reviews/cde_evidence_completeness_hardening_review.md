# CDE Evidence Completeness Hardening Review

## Prompt type
REVIEW

## Scope
BATCH-SYS-ENF-04-CLEAN — harden Closure Decision Engine (CDE) and immediate promotion consumers so promotion-capable outcomes require complete governed evidence and fail closed when evidence is missing or malformed.

## Evidence now required for promotion-capable CDE decisions
Promotion-capable output is `decision_type=lock`. CDE now requires all of the following before `lock` can be emitted:

1. **Eval summary evidence**
   - At least one governed eval evidence reference (`eval_summary_ref`, `eval_bundle_ref`, or `eval_coverage_summary_ref`).
2. **Required eval completeness and outcomes**
   - `required_eval_statuses` must be present and non-empty.
   - Missing required evals fail closed.
   - Failed required evals fail closed.
   - Indeterminate required evals fail closed unless an explicit policy artifact is provided (`allow_indeterminate_required_evals=true` and `allow_indeterminate_policy_ref`).
3. **Trace completeness**
   - Non-placeholder `trace_id`.
   - Non-empty `traceability_refs`.
4. **Certification evidence (promotion semantics)**
   - When certification is required, `certification_ref` must be present and `certification_status` must be passing.
5. **Replay / consistency evidence (where already modeled)**
   - If `replay_consistency_required=true`, non-empty `replay_consistency_refs` are required.

If any requirement is missing/malformed, CDE emits a non-promotable `blocked` decision with explicit reason codes.

## Fail-open paths closed in this slice
- Closed path where non-`blocked`/non-`escalate` closure decisions were treated as promotable downstream.
- Closed path where review promotion gate could classify safe-to-merge without checking CDE promotability semantics.
- Closed path where lock could be inferred without explicit governed eval/certification/trace evidence completeness.

## Non-promotion path preservation
- CDE evidence completeness checks are only promotion-capability checks for `lock` outcomes.
- Non-promotion CDE decisions (`continue_repair_bounded`, `continue_bounded`, `hardening_required`, `final_verification_required`, `blocked`, `escalate`) remain available without forcing promotion-grade evidence artifacts.
- This preserves honest `completed`/continuation behavior while preventing unsafe readiness claims.

## Contract / compatibility strategy
- No governed schema changes were introduced in this slice.
- Compatibility was preserved by encoding fail-closed semantics using existing `decision_type` and `decision_reason_codes` fields.
- Promotion consumers were tightened to consume existing governed CDE fields instead of adding shadow compatibility fields.

## Consumer hardening performed
- `sequence_transition_policy` now requires `closure_decision_artifact.decision_type == lock` for promotion.
- `sequence_transition_policy` blocks when CDE reason codes indicate incomplete promotion evidence.
- `review_promotion_gate` now requires promotable CDE closure semantics before emitting a clean gate.

## Remaining gaps for future certification-grade rigor
- CDE currently validates evidence structure and semantic status at the artifact-reference level; deeper artifact readability/schema checks remain primarily enforced in promotion transition policy and certification stages.
- A future slice can formalize a dedicated CDE promotion evidence contract object if additional fields need strict schema-level governance.

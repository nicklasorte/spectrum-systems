# AG-03 HITL Review Queue

## Purpose

AG-03 formalizes a deterministic, governed human-in-the-loop handoff path for runtime outcomes that require review before progression.

This slice is **artifact-first**:

`agent/control outcome -> hitl_review_request artifact -> pending_review state`

No UI, notification transport, or review-resolution workflow is implemented in AG-03.

## Canonical artifact

- Contract: `contracts/schemas/hitl_review_request.schema.json`
- Example: `contracts/examples/hitl_review_request.json`
- Manifest registration: `contracts/standards-manifest.json`

Required fields:

- `id` (deterministic)
- `timestamp` (deterministic)
- `status` (`pending_review`, `superseded`, `closed`)
- `source_run_id`
- `trace_id`
- `source_artifact_ids[]`
- `trigger_stage` (`agent`, `eval`, `control`, `enforcement`)
- `trigger_reason`
- `review_type`
- `required_reviewer_role`
- `policy_version_id`
- `schema_version`

## Queue semantics (AG-03 scope)

AG-03 supports the **pending review handoff point only**:

- Runtime emits `hitl_review_request` with `status: pending_review`.
- Runtime marks final execution as `escalated` and `human_review_required: true`.
- Runtime halts normal progression.

Status transitions to `superseded` or `closed` are defined by future slices (AG-04+).

## Trigger conditions implemented

1. **Control non-allow response** (`trigger_stage: control`)
   - If `evaluation_control_decision.system_response != allow`, runtime emits review request.
2. **Policy-required review on valid output** (`trigger_stage: agent`)
   - Runtime can be configured to route valid output to review.
3. **Indeterminate/ambiguous routed to human** (`trigger_stage: eval`)
   - Runtime can route indeterminate eval outcomes to review.
4. **Explicit deterministic test injection** (`trigger_stage: agent`)
   - CLI flag `--force-review-required`.

## Determinism guarantees

- Review ID is deterministic from governed identity payload (`deterministic_id`).
- No random UUID usage in review path.
- Timestamp is deterministic from canonical review payload hash.
- Source artifact references are deduplicated and sorted.
- JSON emission uses sorted keys.

## Difference from AG-02 failure path

- AG-02 is a **failure** artifact path (`agent_failure_record`) for stage errors.
- AG-03 is a **review handoff** artifact path (`hitl_review_request`) for governed escalation.
- AG-03 does not imply runtime failure; it implies controlled pause for human decision.

## AG-04 boundary

AG-03 ends at `pending_review` emission.

Out of scope until AG-04:

- reviewer action capture
- override/resume semantics
- queue state mutation service
- notification and assignment workflows

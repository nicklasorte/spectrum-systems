# AG-04 HITL Override Enforcement

## Purpose

AG-04 closes the governed human-control loop after AG-03. A run that stops at a review-required boundary may only continue when a **valid** `hitl_override_decision` artifact is supplied and accepted.

No override artifact means the run remains in review-required stop (or fails closed when override is mandatory).

## Canonical artifact

- Schema: `contracts/schemas/hitl_override_decision.schema.json`
- Example: `contracts/examples/hitl_override_decision.json`
- Manifest registration: `contracts/standards-manifest.json`

Required fields (all required, `additionalProperties: false`):

- `artifact_type` = `hitl_override_decision`
- `schema_version` = `1.0.0`
- `override_decision_id`
- `created_at`
- `trace_id`
- `review_request_id`
- `related_execution_record_id`
- `decision_status`
- `decision_reason`
- `decided_by`
- `decision_scope`
- `allowed_next_action`
- `trace_refs`
- `related_artifact_refs`

## Allowed decisions and bounded outcomes

`decision_status` is tightly bounded to:

- `allow_once`
- `deny`
- `require_rerun`
- `require_revision`

`allowed_next_action` must match exactly:

- `allow_once` -> `resume_once`
- `deny` -> `remain_blocked`
- `require_rerun` -> `rerun_from_context`
- `require_revision` -> `revise_input_then_rerun`

Any mismatch is rejected fail-closed.

## Enforcement rules

At every AG-03 review gate (`forced_review_required`, `policy_review_required`, `indeterminate_outcome_routed_to_human`, `control_non_allow_response`):

1. Runtime emits canonical `hitl_review_request` and review-stop `final_execution_record` context.
2. If override enforcement is requested, runtime loads override artifact(s).
3. Runtime requires exactly one valid override artifact.
4. Runtime validates schema and semantic compatibility:
   - trace id must match
   - review request id must match
   - related execution record id must match
   - decision scope must be `ag_runtime_review_boundary`
   - trigger compatibility must match bounded matrix
5. Runtime applies only bounded behavior:
   - `allow_once`: continue exactly once through control/enforcement.
   - other statuses: stop without control/enforcement continuation.

## Fail-closed behavior

These conditions hard-fail closed with `final_execution_record.actions_taken[].action_type = hitl_override_enforcement_failed`:

- missing required override artifact
- unreadable/malformed JSON
- schema-invalid artifact
- multiple override artifacts (ambiguous selection)
- incompatible semantics (status/action mismatch, wrong IDs, out-of-scope decision)

No default resume path exists.

## Replay/determinism

- Replay with identical input + same valid override artifact produces deterministic control/enforcement IDs.
- Replay without required override cannot bypass review boundary.
- Multiple supplied overrides are rejected deterministically (`override_ambiguous`).

## CLI exercise

Review-required stop (AG-03 behavior preserved):

```bash
python scripts/run_agent_golden_path.py \
  --force-review-required \
  --output-dir /tmp/ag04-review-required
```

Review-required with mandatory override (fails closed if missing):

```bash
python scripts/run_agent_golden_path.py \
  --force-review-required \
  --require-override-decision \
  --output-dir /tmp/ag04-missing-override
```

Review-required with explicit override artifact:

```bash
python scripts/run_agent_golden_path.py \
  --force-review-required \
  --require-override-decision \
  --override-decision-path /tmp/ag04-cli-build/override.json \
  --output-dir /tmp/ag04-with-override
```

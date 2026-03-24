# AG-01 Agent Runtime Golden Path (AG-02 Failure-Hardened, AG-03 HITL Review Queue)

## Purpose

`AG-01` defines the **single canonical runtime path** for governed agent execution:

`context_bundle -> agent_execution_trace -> structured_output -> eval -> eval_summary -> control_decision -> enforcement -> final_execution_record`

`AG-02` hardens this path so every failure emits one canonical governed failure artifact.

`AG-03` adds deterministic human-in-the-loop handoff semantics so review-required outcomes emit a governed review request and halt normal progression.

## Pipeline diagram (text)

1. **Context assembly**
   - Build `context_bundle` with `build_context_bundle(...)`.
   - Validate against `context_bundle` contract.
2. **Agent execution**
   - Execute bounded plan with `execute_step_sequence(...)`.
   - Emit `agent_execution_trace`.
3. **Output normalization**
   - Normalize to `structured_output` as a governed `eval_case` artifact.
   - Validate schema.
4. **Eval execution**
   - Run `run_eval_case(...)` + `compute_eval_summary(...)`.
   - Emit `eval_result` and `eval_summary`.
5. **AG-03 review gate (pre-control)**
   - If forced review, policy-required review, or indeterminate routing condition is met:
     - emit `hitl_review_request`
     - emit escalated `final_execution_record`
     - stop before control/enforcement.
6. **Control decision**
   - Run `run_control_loop(eval_summary, ...)`.
   - Emit `evaluation_control_decision` (`control_decision`).
7. **AG-03 review gate (control)**
   - If control `system_response != allow`:
     - emit `hitl_review_request`
     - emit escalated `final_execution_record`
     - stop before enforcement.
8. **Enforcement**
   - Apply `enforce_control_decision(...)` only for `allow`.
9. **Final execution record**
   - Emit `final_execution_record` as `control_execution_result` (`success` path).

## Failure stages (AG-02)

Canonical `failure_stage` vocabulary:

- `context`
- `agent`
- `normalization`
- `eval`
- `control`
- `enforcement`

At any stage failure:

1. Build `agent_failure_record`.
2. Emit `failure_artifact.json`.
3. Stop pipeline immediately.
4. Do not execute downstream stages.

## Review-required stages (AG-03)

Canonical review triggers:

- `forced_review_required` (CLI/test injection)
- `policy_review_required` (policy marks valid output for review)
- `indeterminate_outcome_routed_to_human` (ambiguous/indeterminate eval route)
- `control_non_allow_response` (control decision is `warn/freeze/block`)

At review-required stop:

1. Build `hitl_review_request` (`status: pending_review`).
2. Emit `hitl_review_request.json`.
3. Emit `final_execution_record` with `execution_status: escalated` and `human_review_required: true`.
4. Stop progression; no enforcement artifact is emitted for this path.

## Canonical AG-03 review artifact

`artifact_type: hitl_review_request` (`schema_version: 1.0.0`)

Required fields:

- `id` (deterministic)
- `timestamp` (deterministic)
- `status` (`pending_review | superseded | closed`)
- `source_run_id`
- `trace_id`
- `source_artifact_ids[]`
- `trigger_stage` (`agent | eval | control | enforcement`)
- `trigger_reason`
- `review_type`
- `required_reviewer_role`
- `policy_version_id`
- `schema_version`

Governance guarantees:

- Schema-valid against `contracts/schemas/hitl_review_request.schema.json`
- `additionalProperties: false`
- Deterministic identity (`deterministic_id`, no random UUIDs)
- Stable ordering for emitted JSON keys

## Artifact flow

On successful run, artifacts are emitted to the output directory:

- `context_bundle.json`
- `agent_execution_trace.json`
- `structured_output.json` (schema-valid `eval_case`)
- `eval_result.json`
- `eval_summary.json`
- `control_decision.json`
- `enforcement.json`
- `final_execution_record.json`

On fail-closed stage failure, `failure_artifact.json` is emitted and downstream stages are not executed.

On review-required stop, `hitl_review_request.json` + escalated `final_execution_record.json` are emitted and enforcement is not executed.

## CLI behavior

`scripts/run_agent_golden_path.py` behavior:

- Exit `0` on success with concise artifact list.
- Exit `1` on stage failure with concise failure summary.
- Exit `2` on review-required handoff with concise review summary.
- `--force-review-required` provides deterministic test injection for AG-03 path.

## Run locally

```bash
python scripts/run_agent_golden_path.py \
  --task-type meeting_minutes \
  --input-json '{"transcript":"Golden path runtime input"}' \
  --source-artifacts-json '[{"artifact_id":"artifact-001"}]' \
  --output-dir outputs/agent_golden_path
```

Review-path examples:

```bash
python scripts/run_agent_golden_path.py --force-review-required
python scripts/run_agent_golden_path.py --policy-review-required
python scripts/run_agent_golden_path.py --force-indeterminate-review
python scripts/run_agent_golden_path.py --force-eval-status fail --force-control-block
```

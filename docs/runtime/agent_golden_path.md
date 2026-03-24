# AG-01 Agent Runtime Golden Path (AG-02 Failure-Hardened)

## Purpose

`AG-01` defines the **single canonical runtime path** for governed agent execution:

`context_bundle -> agent_execution_trace -> structured_output -> eval -> eval_summary -> control_decision -> enforcement -> final_execution_record`

`AG-02` hardens this path so every failure emits one canonical governed failure artifact.

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
5. **Control decision**
   - Run `run_control_loop(eval_summary, ...)`.
   - Emit `evaluation_control_decision` (`control_decision`).
6. **Enforcement**
   - Apply `enforce_control_decision(...)`.
   - `allow/warn` proceeds, `freeze/block` halts.
7. **Final execution record**
   - Emit `final_execution_record` as `control_execution_result`.

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

## Canonical failure artifact

`artifact_type: agent_failure_record` (`schema_version: 1.0.0`)

Required fields:

- `id` (deterministic)
- `timestamp` (deterministic)
- `run_id`
- `trace_id`
- `failure_stage`
- `failure_type`
- `error_message`
- `root_artifact_ids`
- `input_references`
- `policy_version_id`

Governance guarantees:

- Schema-valid against `contracts/schemas/agent_failure_record.schema.json`
- `additionalProperties: false`
- Deterministic identity (`deterministic_id`, no random UUIDs)
- Stable ordering for emitted JSON keys

### Example failure output (shape)

```json
{
  "artifact_type": "agent_failure_record",
  "schema_version": "1.0.0",
  "id": "afr-...",
  "timestamp": "2026-...Z",
  "run_id": "agrun-...",
  "trace_id": "...",
  "failure_stage": "eval",
  "failure_type": "execution_error",
  "error_message": "forced_eval_execution_failure",
  "root_artifact_ids": {
    "context_bundle_id": "...",
    "agent_run_id": "...",
    "eval_case_id": "...",
    "eval_run_id": null,
    "decision_id": null,
    "enforcement_result_id": null
  },
  "input_references": [
    "context_bundle:...",
    "agent_execution_trace:...",
    "structured_output:..."
  ],
  "policy_version_id": null
}
```

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

On fail-closed stop, `failure_artifact.json` is always emitted and downstream stages are not executed.

## CLI behavior

`scripts/run_agent_golden_path.py` behavior:

- Exit `0` on success with concise artifact list.
- Exit non-zero on failure.
- Print concise failure summary (`failure_stage`, `failure_type`, `message`, `failure_artifact_id`).
- Always write `failure_artifact.json` on failure.

## Run locally

```bash
python scripts/run_agent_golden_path.py \
  --task-type meeting_minutes \
  --input-json '{"transcript":"Golden path runtime input"}' \
  --source-artifacts-json '[{"artifact_id":"artifact-001"}]' \
  --output-dir outputs/agent_golden_path
```

Failure injection examples:

```bash
python scripts/run_agent_golden_path.py --fail-context-assembly
python scripts/run_agent_golden_path.py --fail-agent-execution
python scripts/run_agent_golden_path.py --emit-invalid-structured-output
python scripts/run_agent_golden_path.py --fail-eval-execution
python scripts/run_agent_golden_path.py --fail-control-decision
python scripts/run_agent_golden_path.py --fail-enforcement
```

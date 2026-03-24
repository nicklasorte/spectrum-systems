# AG-01 Agent Runtime Golden Path

## Purpose

`AG-01` defines the **single canonical runtime path** for governed agent execution:

`context_bundle -> agent_execution_trace -> structured_output -> eval -> eval_summary -> control_decision -> enforcement -> final_execution_record`

This path is deterministic, bounded, and fail-closed.

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

On fail-closed stop, `failure_artifact.json` is emitted and downstream stages are not executed.

## Failure behavior

Fail-closed at every stage:

- Context schema invalid -> stop + failure artifact.
- Agent execution failure/blocked trace -> stop + failure artifact.
- Structured output schema invalid -> stop + failure artifact.
- Eval stage exception -> stop + failure artifact.
- Control/enforcement errors -> stop + failure artifact.

No silent retries, no hidden fallback, no bypass path.

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
python scripts/run_agent_golden_path.py --fail-agent-execution
python scripts/run_agent_golden_path.py --emit-invalid-structured-output
python scripts/run_agent_golden_path.py --fail-eval-execution
python scripts/run_agent_golden_path.py --force-eval-status fail
```

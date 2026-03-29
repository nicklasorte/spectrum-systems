# MVP-01 — First full trusted Observe → Interpret → Recommend loop

## Intent
Certify one end-to-end meeting-minutes / meeting-intelligence golden path as the canonical first trustworthy system path, from governed input admission through certified output and done-gate artifacts, with no control-loop bypass.

## Why This Slice Exists
Spectrum Systems already has strong local seams (context admission, agent golden path execution, eval/control, enforcement, replay, certification, and observability), but they are not yet specified as one mandatory executable contract for a single canonical path.

MVP-01 exists to prove that one complete governed path can move from input to certified output with:
- traceability (artifact lineage and trace linkage)
- replayability (deterministic replay evidence)
- eval gating (required eval summary + grounding checks)
- control authority (single promotion authority via control decision)
- enforcement (decision-to-action bridge is mandatory)
- certification (control-loop certification pack + done certification)
- observability (records/metrics that explain why the run passed or blocked)

## Scope In
Only the minimum required for one complete meeting-minutes/meeting-intelligence golden path:
- governed input admission via context admission decision artifacts
- deterministic context bundle construction and validation
- bounded execution through the canonical meeting-minutes + agent golden path seam
- structured outputs for meeting intelligence/minutes
- required output evaluation and grounding/contradiction checks on the output path
- mandatory evaluation control decision as promotion authority
- mandatory evaluation enforcement bridge outcome
- replay evidence bound to the same run/trace
- control-loop certification pack and done-gate certification artifacts
- observability records/metrics + persisted trace sufficient to explain end-to-end lineage and decisions

## Scope Out
Explicitly excluded from MVP-01:
- multi-queue scaling or throughput optimization
- generalized multi-agent expansion beyond this single golden path
- broad ecosystem expansion beyond meeting-minutes/meeting-intelligence path hardening
- new model-routing experimentation beyond existing governed adapter/registry behavior
- new subsystem creation unless absolutely required to complete this single path
- broad refactors outside the declared golden-path seams

## Existing Repo Seams To Inspect First
- `docs/roadmap/system_roadmap.md`
- `docs/roadmap/roadmap_step_contract.md`
- `docs/roadmap/pqx_execution_map.md`
- `docs/roadmap/slices/_TEMPLATE.md`
- `spectrum_systems/modules/meeting_minutes_pipeline.py`
- `spectrum_systems/modules/artifact_packager.py`
- `spectrum_systems/modules/runtime/context_admission.py`
- `spectrum_systems/modules/runtime/context_bundle.py`
- `spectrum_systems/modules/runtime/agent_golden_path.py`
- `spectrum_systems/modules/agents/agent_executor.py`
- `spectrum_systems/modules/runtime/run_output_evaluation.py`
- `spectrum_systems/modules/runtime/grounding_factcheck_eval.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py`
- `spectrum_systems/modules/runtime/replay_engine.py`
- `spectrum_systems/modules/runtime/trace_engine.py`
- `spectrum_systems/modules/runtime/trace_store.py`
- `spectrum_systems/modules/runtime/observability_metrics.py`
- `spectrum_systems/modules/governance/done_certification.py`
- `scripts/run_agent_golden_path.py`
- `scripts/run_control_loop_certification.py`
- `contracts/examples/meeting_minutes_record.json`
- `contracts/examples/context_bundle.json`
- `contracts/examples/context_admission_decision.json`
- `contracts/examples/eval_summary.json`
- `contracts/examples/evaluation_control_decision.json`
- `contracts/examples/evaluation_enforcement_action.json`
- `contracts/examples/enforcement_result.json`
- `contracts/examples/replay_result.json`
- `contracts/examples/control_loop_certification_pack.json`
- `contracts/examples/done_certification_record.json`
- `contracts/examples/observability_record.json`
- `contracts/examples/observability_metrics.json`
- `tests/test_meeting_minutes_contract.py`
- `tests/test_context_admission.py`
- `tests/test_context_bundle_v2.py`
- `tests/test_agent_golden_path.py`
- `tests/test_run_output_evaluation.py`
- `tests/test_grounding_factcheck_eval.py`
- `tests/test_evaluation_control.py`
- `tests/test_evaluation_enforcement_bridge.py`
- `tests/test_replay_engine.py`
- `tests/test_control_loop_certification.py`
- `tests/test_done_certification.py`
- `tests/test_observability.py`
- `tests/test_observability_metrics.py`
- `tests/test_trace_engine.py`
- `tests/test_trace_store.py`

## Required Contracts
Required artifacts/schemas on the MVP-01 path:
- `contracts/schemas/context_admission_decision.schema.json`
- `contracts/schemas/context_validation_result.schema.json`
- `contracts/schemas/context_bundle.schema.json`
- `contracts/schemas/meeting_minutes_record.schema.json`
- `contracts/schemas/transcript_intelligence_pack.schema.json`
- `contracts/schemas/agent_execution_trace.schema.json`
- `contracts/schemas/agent_failure_record.schema.json` (fail path)
- `contracts/schemas/ai_model_request.schema.json` (if model-adapter path is exercised)
- `contracts/schemas/ai_model_response.schema.json` (if model-adapter path is exercised)
- `contracts/schemas/eval_case.schema.json`
- `contracts/schemas/eval_run.schema.json`
- `contracts/schemas/eval_result.schema.json`
- `contracts/schemas/eval_summary.schema.json`
- `contracts/schemas/grounding_factcheck_eval.schema.json`
- `contracts/schemas/evaluation_control_decision.schema.json`
- `contracts/schemas/evaluation_enforcement_action.schema.json`
- `contracts/schemas/enforcement_result.schema.json`
- `contracts/schemas/replay_execution_record.schema.json`
- `contracts/schemas/replay_result.schema.json`
- `contracts/schemas/control_loop_certification_pack.schema.json`
- `contracts/schemas/done_certification_record.schema.json`
- `contracts/schemas/done_certification_error.schema.json` (fail path)
- `contracts/schemas/trace.schema.json`
- `contracts/schemas/persisted_trace.schema.json`
- `contracts/schemas/observability_record.schema.json`
- `contracts/schemas/observability_metrics.schema.json`
- `contracts/schemas/artifact_lineage.schema.json`

## Inputs
Artifact-level upstream inputs only:
- raw meeting transcript input artifact for the canonical meeting-minutes run
- context admission input artifacts:
  - `context_bundle`
  - policy selector/version references required by context admission and policy registry
- optional model invocation boundary artifacts when path uses runtime adapter:
  - `ai_model_request`
  - `ai_model_response`
- path configuration references for eval policy / grounding policy / control policy (versioned artifacts or static policy snapshots already used by current seams)
- any prior context artifacts explicitly referenced by the context bundle provenance chain

## Outputs
Required artifacts for a successful MVP-01 run:
- governed meeting output artifacts (`meeting_minutes_record`, plus any bound transcript intelligence artifact used on path)
- `agent_execution_trace`
- evaluation artifacts (`eval_run`, `eval_result`, `eval_summary`, and grounding artifact)
- `evaluation_control_decision`
- enforcement artifacts (`evaluation_enforcement_action`, `enforcement_result`)
- replay artifacts (`replay_execution_record`, `replay_result`)
- certification artifacts (`control_loop_certification_pack`, `done_certification_record`)
- observability artifacts (`observability_record`, `observability_metrics`, `persisted_trace`, lineage links)

## Files Likely To Change
Expected MVP-01 hardening/integration touch points (do not broaden without a new PLAN step):
- `spectrum_systems/modules/runtime/agent_golden_path.py`
- `spectrum_systems/modules/meeting_minutes_pipeline.py`
- `spectrum_systems/modules/runtime/context_admission.py`
- `spectrum_systems/modules/runtime/context_bundle.py`
- `spectrum_systems/modules/runtime/run_output_evaluation.py`
- `spectrum_systems/modules/runtime/grounding_factcheck_eval.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py`
- `spectrum_systems/modules/runtime/replay_engine.py`
- `spectrum_systems/modules/runtime/trace_engine.py`
- `spectrum_systems/modules/runtime/trace_store.py`
- `spectrum_systems/modules/runtime/observability_metrics.py`
- `spectrum_systems/modules/governance/done_certification.py`
- `scripts/run_agent_golden_path.py`
- `scripts/run_control_loop_certification.py`
- `tests/test_agent_golden_path.py`
- `tests/test_meeting_minutes_contract.py`
- `tests/test_run_output_evaluation.py`
- `tests/test_grounding_factcheck_eval.py`
- `tests/test_evaluation_control.py`
- `tests/test_evaluation_enforcement_bridge.py`
- `tests/test_replay_engine.py`
- `tests/test_control_loop_certification.py`
- `tests/test_done_certification.py`
- `tests/test_observability_metrics.py`
- `tests/test_trace_store.py`

## Implementation Tasks
1. Confirm and lock the canonical MVP-01 entrypoint to the existing meeting-minutes golden path (`scripts/run_agent_golden_path.py` + `spectrum_systems/modules/runtime/agent_golden_path.py`) for one governed run profile (`task_type=meeting_minutes`).
2. Ensure context admission is mandatory before execution and emits both `context_validation_result` and `context_admission_decision` with trace/run linkage.
3. Ensure context bundle construction/validation is deterministic and the admitted bundle ID is propagated through downstream artifacts.
4. Ensure bounded execution produces schema-valid meeting-minutes outputs and `agent_execution_trace` (or `agent_failure_record` on failure).
5. Ensure output evaluation executes required eval and grounding checks, including contradiction-sensitive checks already present on the meeting intelligence path.
6. Ensure `evaluation_control_decision` is emitted for every run and is the sole authority for allow/block progression.
7. Ensure evaluation enforcement bridge always emits `evaluation_enforcement_action` + `enforcement_result` and fails closed when decision input is missing/invalid.
8. Ensure replay execution is attached to the same trace/run and emits `replay_execution_record` + `replay_result` for determinism evidence.
9. Ensure control-loop certification pack is assembled from the same governed run evidence, not from synthetic/unlinked artifacts.
10. Ensure done certification emits `done_certification_record` on pass and `done_certification_error` on block/failure paths.
11. Ensure observability artifacts (`observability_record`, `observability_metrics`, `persisted_trace`) explain lineage and control outcomes end-to-end.
12. Add/tighten tests for golden success path and explicit fail-closed cases (missing admission, missing eval summary, missing control decision, missing enforcement artifact, missing replay evidence, incomplete certification pack, missing done certification, broken observability lineage).
13. Run changed-scope verification and confirm only declared MVP-01 files changed.

## Validation Commands
- `test -f docs/roadmap/slices/MVP-01.md`
- `pytest tests/test_roadmap_step_contract.py`
- `python scripts/check_roadmap_authority.py`
- `pytest tests/test_meeting_minutes_contract.py`
- `pytest tests/test_context_admission.py tests/test_context_bundle_v2.py`
- `pytest tests/test_agent_golden_path.py tests/test_agent_executor.py`
- `pytest tests/test_run_output_evaluation.py tests/test_grounding_factcheck_eval.py`
- `pytest tests/test_evaluation_control.py tests/test_evaluation_enforcement_bridge.py`
- `pytest tests/test_replay_engine.py tests/test_control_loop_certification.py`
- `pytest tests/test_done_certification.py tests/test_observability_metrics.py tests/test_trace_store.py`
- `.codex/skills/verify-changed-scope/run.sh`

## Failure Modes (Fail-Closed)
- Context admitted without required validation artifacts (`context_validation_result`, `context_admission_decision`) → block run.
- Context bundle missing/invalid/non-deterministic for same input provenance → block run.
- Execution output missing required schema validity (`meeting_minutes_record` / transcript intelligence output) → block run.
- `agent_execution_trace` missing for successful execution path → block run.
- Required eval artifacts missing (`eval_result`/`eval_summary`) → block run.
- Grounding/contradiction checks missing or invalid on required path → block run.
- `evaluation_control_decision` missing, invalid, or bypassed → block run.
- Enforcement action/result missing after control decision → block run.
- Replay artifacts missing or trace/run mismatch (`replay_execution_record`, `replay_result`) → block run.
- Certification pack missing required linked evidence → block run.
- Done certification missing (`done_certification_record` on pass or `done_certification_error` on block) → block run.
- Observability/trace artifacts unable to explain artifact lineage and decisions → block run.

## Definition of Done
MVP-01 is complete only if all of the following are true (binary pass/fail):
- One governed meeting-minutes/meeting-intelligence run executes from input to final gate with no manual bypass.
- The run produces all required linked artifacts: context admission, context bundle, bounded execution trace, eval summary, control decision, enforcement artifact, replay artifact, certification pack, done certification record, and observability records.
- Every required artifact validates against its governing schema contract.
- Required fail-closed tests prove the run blocks when any mandatory artifact or gate is missing/invalid.
- All listed validation commands pass.

## Non-Goals
PQX must not:
- redesign roadmap structure or replace authoritative roadmap mechanics
- expand to multiple queues or generalized multi-agent orchestration
- introduce new unconstrained model routing paths
- alter unrelated modules/contracts/tests outside MVP-01 seams
- ship convenience bypasses around eval/control/enforcement/certification gates

## Delivery Contract
PQX must return, in a structured report:
1. intent
2. files changed
3. contracts touched
4. path entrypoint used
5. tests/validation run
6. fail-closed cases covered
7. known gaps remaining

"""AG-01 Agent Runtime Golden Path.

Canonical bounded execution path:
context_bundle -> agent_execution_trace -> structured_output(eval_case)
-> eval_result(s) -> eval_summary -> control_decision -> enforcement
-> final execution record.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import NAMESPACE_URL, uuid5

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.agents.agent_executor import execute_step_sequence, generate_step_plan
from spectrum_systems.modules.ai_workflow.context_assembly import build_context_bundle
from spectrum_systems.modules.evaluation.eval_engine import compute_eval_summary, run_eval_case
from spectrum_systems.modules.runtime.control_loop import run_control_loop
from spectrum_systems.modules.runtime.enforcement_engine import enforce_control_decision
from spectrum_systems.utils.deterministic_id import deterministic_id


class AgentGoldenPathError(RuntimeError):
    """Fail-closed error for AG-01 runtime pipeline."""


class AgentGoldenPathStageError(AgentGoldenPathError):
    """Typed fail-closed stage failure for AG-02 canonical artifact emission."""

    def __init__(self, *, stage: str, failure_type: str, error_message: str) -> None:
        super().__init__(error_message)
        self.stage = stage
        self.failure_type = failure_type
        self.error_message = error_message


@dataclass(frozen=True)
class GoldenPathConfig:
    """Runtime configuration for deterministic AG-01 execution."""

    task_type: str
    input_payload: Dict[str, Any]
    source_artifacts: List[Dict[str, Any]]
    context_config: Dict[str, Any]
    output_dir: Path
    fail_context_assembly: bool = False
    fail_agent_execution: bool = False
    emit_invalid_structured_output: bool = False
    fail_eval_execution: bool = False
    emit_invalid_eval_summary: bool = False
    fail_control_decision: bool = False
    fail_enforcement: bool = False
    force_eval_status: Optional[str] = None
    force_control_block: bool = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_contract(payload: Dict[str, Any], schema_name: str, *, stage: str) -> None:
    schema = load_schema(schema_name)
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    except ValidationError as exc:
        raise AgentGoldenPathStageError(
            stage=stage,
            failure_type="schema_error",
            error_message=f"{schema_name} validation failed: {exc.message}",
        ) from exc


def _stable_trace_id(task_type: str, input_payload: Dict[str, Any]) -> str:
    seed = json.dumps({"task_type": task_type, "input_payload": input_payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(uuid5(NAMESPACE_URL, f"ag01-trace::{seed}"))


def _emit_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _deterministic_timestamp(seed_payload: Dict[str, Any]) -> str:
    canonical = json.dumps(seed_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_root_artifact_ids(artifacts: Dict[str, Dict[str, Any]], run_id: str) -> Dict[str, Optional[str]]:
    return {
        "context_bundle_id": artifacts.get("context_bundle", {}).get("context_id"),
        "agent_run_id": artifacts.get("agent_execution_trace", {}).get("agent_run_id") or run_id,
        "eval_case_id": artifacts.get("structured_output", {}).get("eval_case_id"),
        "eval_run_id": artifacts.get("eval_summary", {}).get("eval_run_id"),
        "decision_id": artifacts.get("control_decision", {}).get("decision_id"),
        "enforcement_result_id": artifacts.get("enforcement", {}).get("enforcement_result_id"),
    }


def _build_failure_artifact(
    *,
    run_id: str,
    trace_id: str,
    stage: str,
    failure_type: str,
    error_message: str,
    artifacts: Dict[str, Dict[str, Any]],
    refs: List[str],
    policy_version_id: Optional[str],
) -> Dict[str, Any]:
    root_artifact_ids = _extract_root_artifact_ids(artifacts, run_id)
    identity_payload = {
        "run_id": run_id,
        "trace_id": trace_id,
        "failure_stage": stage,
        "failure_type": failure_type,
        "error_message": error_message,
        "root_artifact_ids": root_artifact_ids,
        "input_references": sorted(set(refs)),
        "policy_version_id": policy_version_id,
    }
    artifact = {
        "artifact_type": "agent_failure_record",
        "schema_version": "1.0.0",
        "id": deterministic_id(
            prefix="afr",
            namespace="agent_golden_path_failure",
            payload=identity_payload,
        ),
        "timestamp": _deterministic_timestamp(identity_payload),
        "run_id": run_id,
        "trace_id": trace_id,
        "failure_stage": stage,
        "failure_type": failure_type,
        "error_message": error_message,
        "root_artifact_ids": root_artifact_ids,
        "input_references": sorted(set(refs)),
        "policy_version_id": policy_version_id,
    }
    _validate_contract(artifact, "agent_failure_record", stage="enforcement")
    return artifact


def _build_structured_output(
    *,
    trace_id: str,
    run_id: str,
    context_bundle: Dict[str, Any],
    tool_calls: List[Dict[str, Any]],
    force_invalid: bool,
    force_eval_status: Optional[str],
) -> Dict[str, Any]:
    eval_case_id = deterministic_id(
        prefix="ec",
        namespace="agent_golden_path_eval_case",
        payload={"run_id": run_id, "context_id": context_bundle["context_id"], "tool_calls": tool_calls},
    )
    structured_output = {
        "artifact_type": "eval_case",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "eval_case_id": eval_case_id,
        "input_artifact_refs": [
            f"context_bundle:{context_bundle['context_id']}",
            f"agent_execution_trace:{run_id}",
        ],
        "expected_output_spec": {
            "forced_status": force_eval_status or "pass",
            "forced_score": 1.0 if (force_eval_status or "pass") == "pass" else 0.0,
        },
        "scoring_rubric": {
            "name": "ag01_runtime_golden_path",
            "version": "1.0.0",
            "dimensions": ["traceability", "schema_validity", "determinism"],
        },
        "evaluation_type": "deterministic",
        "created_from": "synthetic",
        "tool_call_count": len(tool_calls),
    }
    if force_invalid:
        structured_output.pop("evaluation_type", None)
    return structured_output


def run_agent_golden_path(config: GoldenPathConfig) -> Dict[str, Dict[str, Any]]:
    """Execute the AG-01 canonical runtime pipeline and emit governed artifacts."""
    trace_id = _stable_trace_id(config.task_type, config.input_payload)
    run_id = deterministic_id(
        prefix="agrun",
        namespace="agent_golden_path",
        payload={"task_type": config.task_type, "input_payload": config.input_payload, "source_artifacts": config.source_artifacts},
    )

    artifacts: Dict[str, Dict[str, Any]] = {}
    refs: List[str] = []

    try:
        # 1) Context assembly
        try:
            if config.fail_context_assembly:
                raise RuntimeError("forced_context_assembly_failure")
            context_bundle = build_context_bundle(
                config.task_type,
                config.input_payload,
                source_artifacts=config.source_artifacts,
                config=config.context_config,
            )
            _validate_contract(context_bundle, "context_bundle", stage="context")
        except AgentGoldenPathStageError:
            raise
        except Exception as exc:
            raise AgentGoldenPathStageError(
                stage="context",
                failure_type="execution_error",
                error_message=str(exc),
            ) from exc
        artifacts["context_bundle"] = context_bundle
        refs.append(f"context_bundle:{context_bundle['context_id']}")

        # 2) Agent execution (bounded)
        step_plan = generate_step_plan(
            context_bundle,
            [
                {
                    "step_id": "step-001",
                    "step_type": "tool",
                    "tool_name": "generate_structured_signal",
                    "input_ref": f"context://{context_bundle['context_id']}",
                    "tool_input": {"context_id": context_bundle["context_id"]},
                }
            ],
        )

        def _tool_fn(payload: Dict[str, Any]) -> Dict[str, Any]:
            if config.fail_agent_execution:
                raise RuntimeError("forced_agent_execution_failure")
            return {
                "artifact_id": deterministic_id(
                    prefix="tool",
                    namespace="agent_golden_path",
                    payload={"run_id": run_id, "payload": payload},
                ),
                "artifact_type": "tool_output",
                "schema_name": "artifact_envelope",
                "payload": deepcopy(payload),
            }

        try:
            trace = execute_step_sequence(
                agent_run_id=run_id,
                trace_id=trace_id,
                context_bundle=context_bundle,
                step_plan=step_plan,
                final_output_schema="eval_case",
                tool_registry={"generate_structured_signal": _tool_fn},
                final_output_builder=lambda bundle, steps: _build_structured_output(
                    trace_id=trace_id,
                    run_id=run_id,
                    context_bundle=bundle,
                    tool_calls=[s for s in steps if s.get("step_type") == "tool"],
                    force_invalid=False,
                    force_eval_status=config.force_eval_status,
                ),
            )
            if trace["execution_status"] != "completed":
                raise RuntimeError(trace.get("failure_reason") or "agent execution did not complete")
        except Exception as exc:
            raise AgentGoldenPathStageError(
                stage="agent",
                failure_type="execution_error",
                error_message=str(exc),
            ) from exc
        artifacts["agent_execution_trace"] = trace
        refs.append(f"agent_execution_trace:{trace['agent_run_id']}")

        # 3) Output normalization
        structured_output = _build_structured_output(
            trace_id=trace_id,
            run_id=run_id,
            context_bundle=context_bundle,
            tool_calls=trace["tool_calls"],
            force_invalid=config.emit_invalid_structured_output,
            force_eval_status=config.force_eval_status,
        )
        _validate_contract(structured_output, "eval_case", stage="normalization")
        artifacts["structured_output"] = structured_output
        refs.append(f"structured_output:{structured_output['eval_case_id']}")

        # 4) Eval execution
        try:
            if config.fail_eval_execution:
                raise RuntimeError("forced_eval_execution_failure")
            eval_result = run_eval_case(structured_output)
            _validate_contract(eval_result, "eval_result", stage="eval")
            eval_summary = compute_eval_summary(
                eval_run_id=run_id,
                trace_id=trace_id,
                eval_results=[eval_result],
            )
            if config.emit_invalid_eval_summary:
                eval_summary.pop("trace_id", None)
            if config.force_control_block:
                eval_summary["reproducibility_score"] = 0.0
                eval_summary["system_status"] = "failing"
            _validate_contract(eval_summary, "eval_summary", stage="eval")
        except AgentGoldenPathStageError:
            raise
        except Exception as exc:
            raise AgentGoldenPathStageError(
                stage="eval",
                failure_type="execution_error",
                error_message=str(exc),
            ) from exc
        artifacts["eval_result"] = eval_result
        artifacts["eval_summary"] = eval_summary
        refs.append(f"eval_result:{eval_result['eval_case_id']}")
        refs.append(f"eval_summary:{eval_summary['eval_run_id']}")

        # 5) Control decision
        try:
            if config.fail_control_decision:
                raise RuntimeError("forced_control_decision_failure")
            control = run_control_loop(eval_summary, {"run_id": run_id, "trace_id": trace_id})
            decision = control["evaluation_control_decision"]
            _validate_contract(decision, "evaluation_control_decision", stage="control")
        except AgentGoldenPathStageError:
            raise
        except Exception as exc:
            raise AgentGoldenPathStageError(
                stage="control",
                failure_type="policy_error",
                error_message=str(exc),
            ) from exc
        artifacts["control_decision"] = decision
        refs.append(f"evaluation_control_decision:{decision['decision_id']}")

        # 6) Enforcement
        try:
            if config.fail_enforcement:
                raise RuntimeError("forced_enforcement_failure")
            enforcement = enforce_control_decision(decision)
            _validate_contract(enforcement, "enforcement_result", stage="enforcement")
        except AgentGoldenPathStageError:
            raise
        except Exception as exc:
            raise AgentGoldenPathStageError(
                stage="enforcement",
                failure_type="execution_error",
                error_message=str(exc),
            ) from exc
        artifacts["enforcement"] = enforcement
        refs.append(f"enforcement_result:{enforcement['enforcement_result_id']}")

        system_response = str(decision.get("system_response", "block"))
        continuation_allowed = system_response in {"allow", "warn"}
        warning_flag = system_response == "warn"

        # 7) Final execution record
        execution_record = {
            "trace_id": trace_id,
            "run_id": run_id,
            "artifact_id": deterministic_id(
                prefix="cer",
                namespace="agent_golden_path_execution",
                payload={"run_id": run_id, "trace_id": trace_id, "decision_id": decision["decision_id"]},
            ),
            "execution_status": "success" if continuation_allowed else "blocked",
            "actions_taken": [
                {
                    "action_type": "agent_golden_path_completed",
                    "status": "proceed" if continuation_allowed else "blocked",
                    "warning": warning_flag,
                    "control_decision": system_response,
                    "artifact_references": sorted(set(refs)),
                    "timestamp": _now_iso(),
                }
            ],
            "validators_run": [
                "context_bundle",
                "agent_execution_trace",
                "eval_case",
                "eval_engine",
                "control_loop",
                "enforcement",
            ],
            "validators_failed": [],
            "repair_actions_applied": [],
            "publication_blocked": not continuation_allowed,
            "decision_blocked": not continuation_allowed,
            "rerun_triggered": False,
            "escalation_triggered": False,
            "human_review_required": warning_flag,
        }
        _validate_contract(execution_record, "control_execution_result", stage="enforcement")
        artifacts["final_execution_record"] = execution_record

    except AgentGoldenPathStageError as exc:
        failure = _build_failure_artifact(
            run_id=run_id,
            trace_id=trace_id,
            stage=exc.stage,
            failure_type=exc.failure_type,
            error_message=exc.error_message,
            artifacts=artifacts,
            refs=refs,
            policy_version_id=None,
        )
        artifacts["failure_artifact"] = failure

    output_paths = {
        "context_bundle": config.output_dir / "context_bundle.json",
        "agent_execution_trace": config.output_dir / "agent_execution_trace.json",
        "structured_output": config.output_dir / "structured_output.json",
        "eval_result": config.output_dir / "eval_result.json",
        "eval_summary": config.output_dir / "eval_summary.json",
        "control_decision": config.output_dir / "control_decision.json",
        "enforcement": config.output_dir / "enforcement.json",
        "final_execution_record": config.output_dir / "final_execution_record.json",
        "failure_artifact": config.output_dir / "failure_artifact.json",
    }
    for key, payload in artifacts.items():
        _emit_json(output_paths[key], payload)

    return artifacts

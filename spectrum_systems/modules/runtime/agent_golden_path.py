"""AG-01 Agent Runtime Golden Path.

Canonical bounded execution path:
context_bundle -> agent_execution_trace -> structured_output(eval_case)
-> eval_result(s) -> eval_summary -> control_decision -> enforcement
-> final execution record.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import NAMESPACE_URL, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.agents.agent_executor import execute_step_sequence, generate_step_plan
from spectrum_systems.modules.ai_workflow.context_assembly import build_context_bundle
from spectrum_systems.modules.evaluation.eval_engine import compute_eval_summary, run_eval_case
from spectrum_systems.modules.runtime.control_loop import run_control_loop
from spectrum_systems.modules.runtime.enforcement_engine import enforce_control_decision
from spectrum_systems.utils.deterministic_id import deterministic_id


class AgentGoldenPathError(RuntimeError):
    """Fail-closed error for AG-01 runtime pipeline."""


@dataclass(frozen=True)
class GoldenPathConfig:
    """Runtime configuration for deterministic AG-01 execution."""

    task_type: str
    input_payload: Dict[str, Any]
    source_artifacts: List[Dict[str, Any]]
    context_config: Dict[str, Any]
    output_dir: Path
    fail_agent_execution: bool = False
    emit_invalid_structured_output: bool = False
    fail_eval_execution: bool = False
    force_eval_status: Optional[str] = None
    force_control_block: bool = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_contract(payload: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def _stable_trace_id(task_type: str, input_payload: Dict[str, Any]) -> str:
    seed = json.dumps({"task_type": task_type, "input_payload": input_payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(uuid5(NAMESPACE_URL, f"ag01-trace::{seed}"))


def _emit_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _failure_record(*, run_id: str, trace_id: str, stage: str, reason: str, artifact_refs: List[str]) -> Dict[str, Any]:
    record = {
        "trace_id": trace_id,
        "run_id": run_id,
        "artifact_id": deterministic_id(
            prefix="cer",
            namespace="agent_golden_path_execution",
            payload={"run_id": run_id, "trace_id": trace_id, "stage": stage, "reason": reason},
        ),
        "execution_status": "blocked",
        "actions_taken": [
            {
                "action_type": "agent_golden_path_failure",
                "status": "blocked",
                "stage": stage,
                "reason": reason,
                "artifact_references": sorted(set(artifact_refs)),
                "timestamp": _now_iso(),
            }
        ],
        "validators_run": ["agent_golden_path"],
        "validators_failed": [stage],
        "repair_actions_applied": [],
        "publication_blocked": True,
        "decision_blocked": True,
        "rerun_triggered": False,
        "escalation_triggered": False,
        "human_review_required": True,
    }
    _validate_contract(record, "control_execution_result")
    return record


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
        context_bundle = build_context_bundle(
            config.task_type,
            config.input_payload,
            source_artifacts=config.source_artifacts,
            config=config.context_config,
        )
        _validate_contract(context_bundle, "context_bundle")
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
                force_invalid=config.emit_invalid_structured_output,
                force_eval_status=config.force_eval_status,
            ),
        )
        artifacts["agent_execution_trace"] = trace
        refs.append(f"agent_execution_trace:{trace['agent_run_id']}")

        if trace["execution_status"] != "completed":
            raise AgentGoldenPathError(trace.get("failure_reason") or "agent execution did not complete")

        # 3) Output normalization
        structured_output = _build_structured_output(
            trace_id=trace_id,
            run_id=run_id,
            context_bundle=context_bundle,
            tool_calls=trace["tool_calls"],
            force_invalid=config.emit_invalid_structured_output,
            force_eval_status=config.force_eval_status,
        )
        _validate_contract(structured_output, "eval_case")
        artifacts["structured_output"] = structured_output
        refs.append(f"structured_output:{structured_output['eval_case_id']}")

        # 4) Eval execution
        if config.fail_eval_execution:
            raise AgentGoldenPathError("forced_eval_execution_failure")
        eval_result = run_eval_case(structured_output)
        _validate_contract(eval_result, "eval_result")
        eval_summary = compute_eval_summary(
            eval_run_id=run_id,
            trace_id=trace_id,
            eval_results=[eval_result],
        )
        if config.force_control_block:
            eval_summary["reproducibility_score"] = 0.0
            eval_summary["system_status"] = "failing"
        _validate_contract(eval_summary, "eval_summary")
        artifacts["eval_result"] = eval_result
        artifacts["eval_summary"] = eval_summary
        refs.append(f"eval_result:{eval_result['eval_case_id']}")
        refs.append(f"eval_summary:{eval_summary['eval_run_id']}")

        # 5) Control decision
        control = run_control_loop(eval_summary, {"run_id": run_id, "trace_id": trace_id})
        decision = control["evaluation_control_decision"]
        _validate_contract(decision, "evaluation_control_decision")
        artifacts["control_decision"] = decision
        refs.append(f"evaluation_control_decision:{decision['decision_id']}")

        # 6) Enforcement
        enforcement = enforce_control_decision(decision)
        _validate_contract(enforcement, "enforcement_result")
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
        _validate_contract(execution_record, "control_execution_result")
        artifacts["final_execution_record"] = execution_record

    except Exception as exc:
        failure = _failure_record(
            run_id=run_id,
            trace_id=trace_id,
            stage=("agent_execution" if "agent_execution_trace" in artifacts else "context_or_precheck"),
            reason=str(exc),
            artifact_refs=refs,
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

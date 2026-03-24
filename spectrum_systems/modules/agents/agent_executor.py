"""Bounded Agent Execution Module (BAZ).

Provides a governed, deterministic execution surface for agent-like workflows:
- consume a validated context bundle
- generate a bounded step plan
- execute declared steps/tools without autonomous looping
- emit a schema-valid execution trace artifact
- validate final output against a declared artifact schema
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

SCHEMA_VERSION = "1.0.0"
TRACE_ARTIFACT_TYPE = "agent_execution_trace"

STEP_STATUS_PLANNED = "planned"
STEP_STATUS_COMPLETED = "completed"
STEP_STATUS_FAILED = "failed"
STEP_STATUS_BLOCKED = "blocked"

EXECUTION_COMPLETED = "completed"
EXECUTION_FAILED = "failed"
EXECUTION_BLOCKED = "blocked"

ToolFn = Callable[[Dict[str, Any]], Dict[str, Any]]


class AgentExecutionError(RuntimeError):
    """Base error for bounded agent execution failures."""


class AgentExecutionBlockedError(AgentExecutionError):
    """Raised when required context or declared tools are unavailable."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_contract(instance: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def construct_context_bundle(context_bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a context bundle for bounded execution.

    Fail-closed rules:
    - context bundle must pass context_bundle contract validation
    - context must include either retrieved_context or prior_artifacts content
    """
    bundle = deepcopy(context_bundle)
    _validate_contract(bundle, "context_bundle")

    has_retrieval = bool(bundle.get("retrieved_context"))
    has_prior = bool(bundle.get("prior_artifacts"))
    if not (has_retrieval or has_prior):
        raise AgentExecutionBlockedError(
            "construct_context_bundle: context bundle missing required execution context "
            "(retrieved_context or prior_artifacts)"
        )

    return bundle


def generate_step_plan(
    context_bundle: Dict[str, Any],
    declared_steps: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Generate a deterministic bounded step plan from declared steps.

    No dynamic step insertion, recursion, or loops are permitted.
    """
    if not declared_steps:
        raise AgentExecutionBlockedError("generate_step_plan: declared_steps must not be empty")

    plan: List[Dict[str, Any]] = []
    for idx, raw_step in enumerate(declared_steps, start=1):
        step_type = str(raw_step.get("step_type") or "").strip()
        if not step_type:
            raise AgentExecutionBlockedError(
                f"generate_step_plan: step at index {idx - 1} missing step_type"
            )

        step_id = str(raw_step.get("step_id") or f"step-{idx:03d}")
        step: Dict[str, Any] = {
            "step_id": step_id,
            "step_type": step_type,
            "status": STEP_STATUS_PLANNED,
            "input_ref": raw_step.get("input_ref", f"context://{context_bundle['context_id']}"),
            "output_ref": raw_step.get("output_ref"),
            "tool_name": raw_step.get("tool_name"),
            "tool_input": deepcopy(raw_step.get("tool_input") or {}),
            "artifact_schema": raw_step.get("artifact_schema"),
        }
        plan.append(step)
    return plan


def execute_tool_step(
    step: Dict[str, Any],
    tool_registry: Dict[str, ToolFn],
) -> Dict[str, Any]:
    """Execute one declared tool step exactly once and capture a governed call log."""
    step_id = step["step_id"]
    tool_name = str(step.get("tool_name") or "").strip()
    input_ref = str(step.get("input_ref") or f"step://{step_id}/input")

    if not tool_name:
        return {
            "step_id": step_id,
            "tool_name": "",
            "input_ref": input_ref,
            "output_ref": None,
            "status": STEP_STATUS_BLOCKED,
            "error": "execute_tool_step: missing tool_name",
            "output": None,
        }

    tool = tool_registry.get(tool_name)
    if tool is None:
        return {
            "step_id": step_id,
            "tool_name": tool_name,
            "input_ref": input_ref,
            "output_ref": None,
            "status": STEP_STATUS_BLOCKED,
            "error": f"execute_tool_step: tool '{tool_name}' is not registered",
            "output": None,
        }

    try:
        output = tool(deepcopy(step.get("tool_input") or {}))
    except Exception as exc:  # explicit fail-closed behavior
        return {
            "step_id": step_id,
            "tool_name": tool_name,
            "input_ref": input_ref,
            "output_ref": None,
            "status": STEP_STATUS_FAILED,
            "error": f"execute_tool_step: tool '{tool_name}' failed: {exc}",
            "output": None,
        }

    output_ref = str(output.get("artifact_id") or f"artifact://{step_id}")
    return {
        "step_id": step_id,
        "tool_name": tool_name,
        "input_ref": input_ref,
        "output_ref": output_ref,
        "status": STEP_STATUS_COMPLETED,
        "error": None,
        "output": deepcopy(output),
    }


def validate_final_output(final_output: Dict[str, Any], schema_name: str) -> None:
    """Validate final output against its declared artifact schema."""
    if not schema_name or not isinstance(schema_name, str):
        raise AgentExecutionError("validate_final_output: schema_name must be a non-empty string")
    _validate_contract(final_output, schema_name)


def emit_agent_execution_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and return an agent execution trace artifact."""
    _validate_contract(trace, "agent_execution_trace")
    return trace


def execute_step_sequence(
    *,
    agent_run_id: str,
    trace_id: str,
    prompt_resolution: Dict[str, Any],
    context_bundle: Dict[str, Any],
    step_plan: Sequence[Dict[str, Any]],
    final_output_schema: str,
    tool_registry: Optional[Dict[str, ToolFn]] = None,
    final_output_builder: Optional[Callable[[Dict[str, Any], List[Dict[str, Any]]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Execute a bounded step sequence and emit a governed execution trace.

    Execution is strictly linear across the declared step_plan.
    Any blocked/failed step stops execution immediately (fail closed).
    """
    if not agent_run_id or not trace_id:
        raise AgentExecutionError("execute_step_sequence: agent_run_id and trace_id are required")

    required_prompt_fields = ("prompt_id", "prompt_version", "resolution_source", "status")
    if not prompt_resolution or any(not str(prompt_resolution.get(field) or "").strip() for field in required_prompt_fields):
        raise AgentExecutionError("execute_step_sequence: prompt_resolution with prompt_id/prompt_version/resolution_source/status is required")

    bounded_context = construct_context_bundle(context_bundle)
    planned_steps = [deepcopy(step) for step in step_plan]

    started_at = _now_iso()
    tool_calls: List[Dict[str, Any]] = []
    intermediate_artifacts: List[Dict[str, Any]] = []
    execution_status = EXECUTION_COMPLETED
    failure_reason: Optional[str] = None

    registry = tool_registry or {}

    for step in planned_steps:
        step["status"] = STEP_STATUS_PLANNED
        step_type = step["step_type"]

        if step_type == "tool":
            call = execute_tool_step(step, registry)
            tool_calls.append(
                {
                    "step_id": call["step_id"],
                    "tool_name": call["tool_name"],
                    "input_ref": call["input_ref"],
                    "output_ref": call["output_ref"],
                    "status": call["status"],
                    "error": call.get("error"),
                }
            )
            step["status"] = call["status"]
            step["output_ref"] = call["output_ref"]
            step["error"] = call.get("error")

            if call["status"] != STEP_STATUS_COMPLETED:
                execution_status = (
                    EXECUTION_BLOCKED if call["status"] == STEP_STATUS_BLOCKED else EXECUTION_FAILED
                )
                failure_reason = call.get("error") or "tool step failed"
                break

            output = call.get("output") or {}
            if output:
                intermediate_artifacts.append(
                    {
                        "artifact_id": str(output.get("artifact_id") or call["output_ref"]),
                        "artifact_type": str(output.get("artifact_type") or "tool_output"),
                        "schema_name": str(output.get("schema_name") or "artifact_envelope"),
                    }
                )

        elif step_type == "transform":
            step["status"] = STEP_STATUS_COMPLETED
            step["output_ref"] = str(step.get("output_ref") or f"transform://{step['step_id']}")
            step["error"] = None
        else:
            step["status"] = STEP_STATUS_BLOCKED
            step["error"] = f"execute_step_sequence: unsupported step_type '{step_type}'"
            execution_status = EXECUTION_BLOCKED
            failure_reason = step["error"]
            break

    completed_at = _now_iso()

    if execution_status == EXECUTION_COMPLETED:
        builder = final_output_builder or (
            lambda bundle, steps: {
                "context_id": bundle["context_id"],
                "task_type": bundle["task_type"],
                "executed_step_ids": [s["step_id"] for s in steps if s.get("status") == STEP_STATUS_COMPLETED],
            }
        )
        final_output = builder(bounded_context, planned_steps)
        try:
            validate_final_output(final_output, final_output_schema)
        except Exception as exc:
            execution_status = EXECUTION_FAILED
            failure_reason = f"validate_final_output failed: {exc}"

    final_output_artifact_id = f"agent-output://{agent_run_id}"
    trace = {
        "agent_run_id": agent_run_id,
        "context_bundle_id": bounded_context["context_id"],
        "trace_id": trace_id,
        "prompt_resolution": {
            "prompt_id": str(prompt_resolution["prompt_id"]),
            "prompt_version": str(prompt_resolution["prompt_version"]),
            "requested_alias": prompt_resolution.get("requested_alias"),
            "resolution_source": str(prompt_resolution["resolution_source"]),
            "status": str(prompt_resolution["status"]),
        },
        "step_sequence": [
            {
                "step_id": s["step_id"],
                "step_type": s["step_type"],
                "status": s["status"],
                "input_ref": s.get("input_ref"),
                "output_ref": s.get("output_ref"),
                "error": s.get("error"),
            }
            for s in planned_steps
        ],
        "tool_calls": tool_calls,
        "intermediate_artifacts": intermediate_artifacts,
        "final_output_artifact_id": final_output_artifact_id,
        "execution_status": execution_status,
        "failure_reason": failure_reason,
        "started_at": started_at,
        "completed_at": completed_at,
    }
    return emit_agent_execution_trace(trace)

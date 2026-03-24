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
from spectrum_systems.modules.runtime.context_bundle import (
    ContextBundleValidationError,
    compose_context_bundle,
    validate_context_bundle,
)
from spectrum_systems.modules.runtime.model_adapter import (
    CanonicalModelAdapter,
    ModelAdapterError,
    build_canonical_request,
)
from spectrum_systems.modules.runtime.prompt_injection_defense import (
    PromptInjectionDefenseError,
    assess_prompt_injection,
    default_prompt_injection_policy,
    evaluate_enforcement_outcome,
)
from spectrum_systems.modules.runtime.multi_pass_generation import (
    MultiPassGenerationError,
    run_multi_pass_generation,
)

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


def construct_context_bundle(
    context_bundle: Dict[str, Any],
    *,
    trace_id: str,
    run_id: str,
) -> Dict[str, Any]:
    """Validate and normalize a context bundle for bounded execution.

    Fail-closed rules:
    - context bundle must pass context_bundle contract validation
    - context must include either retrieved_context or prior_artifacts content
    """
    bundle = deepcopy(context_bundle)

    if "context_items" not in bundle:
        bundle = compose_context_bundle(
            task_type=str(bundle.get("task_type") or ""),
            input_payload=dict(bundle.get("primary_input") or {}),
            policy_constraints=bundle.get("policy_constraints") or {},
            retrieved_context=list(bundle.get("retrieved_context") or []),
            prior_artifacts=list(bundle.get("prior_artifacts") or []),
            glossary_terms=list(bundle.get("glossary_terms") or []),
            unresolved_questions=list(bundle.get("unresolved_questions") or []),
            source_artifact_ids=list(((bundle.get("metadata") or {}).get("source_artifact_ids") or [])),
            trace_id=trace_id,
            run_id=run_id,
            glossary_registry_entries=list(bundle.get("glossary_registry_entries") or []),
            glossary_injection_policy=dict(bundle.get("glossary_injection_policy") or {}),
        )

    # Ensure runtime linkage fields are explicit and up to date at execution seam.
    bundle.setdefault("trace", {})
    bundle["trace"]["trace_id"] = trace_id
    bundle["trace"]["run_id"] = run_id
    bundle.setdefault("glossary_terms", [])
    bundle.setdefault("glossary_definitions", [])
    bundle.setdefault(
        "glossary_canonicalization",
        {
            "injection_enabled": False,
            "match_mode": "exact",
            "selection_mode": "explicit_then_exact_text",
            "fail_on_missing_required": False,
            "selected_glossary_entry_ids": [],
            "unresolved_terms": [],
        },
    )
    bundle.setdefault("metadata", {})
    if isinstance(bundle["metadata"], dict):
        bundle["metadata"].setdefault("glossary_injection_status", "not_requested")
    bundle.setdefault("token_estimates", {})
    if isinstance(bundle["token_estimates"], dict):
        bundle["token_estimates"].setdefault("glossary_definitions", 0)
        bundle["token_estimates"].setdefault(
            "total",
            sum(
                int(bundle["token_estimates"].get(name, 0))
                for name in (
                    "primary_input",
                    "policy_constraints",
                    "prior_artifacts",
                    "retrieved_context",
                    "glossary_terms",
                    "glossary_definitions",
                    "unresolved_questions",
                )
            ),
        )

    try:
        _validate_contract(bundle, "context_bundle")
        validate_context_bundle(bundle)
    except (ContextBundleValidationError, Exception) as exc:
        raise AgentExecutionBlockedError(f"construct_context_bundle: {exc}") from exc

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
            "requested_model_id": raw_step.get("requested_model_id"),
            "input_text": raw_step.get("input_text"),
            "execution_constraints": deepcopy(raw_step.get("execution_constraints") or {}),
            "requires_structured_generation": bool(raw_step.get("requires_structured_generation", False)),
            "structured_output": deepcopy(raw_step.get("structured_output")),
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
    model_adapter: Optional[CanonicalModelAdapter] = None,
    final_output_builder: Optional[Callable[[Dict[str, Any], List[Dict[str, Any]]], Dict[str, Any]]] = None,
    routing_decision: Optional[Dict[str, Any]] = None,
    prompt_injection_policy: Optional[Dict[str, Any]] = None,
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
    required_routing_fields = ("routing_decision_id", "policy_id", "route_key", "task_class", "selected_model_id")
    if not routing_decision or any(not str(routing_decision.get(field) or "").strip() for field in required_routing_fields):
        raise AgentExecutionError(
            "execute_step_sequence: routing_decision with routing_decision_id/policy_id/route_key/task_class/selected_model_id is required"
        )

    bounded_context = construct_context_bundle(context_bundle, trace_id=trace_id, run_id=agent_run_id)
    injection_policy = dict(prompt_injection_policy or default_prompt_injection_policy())
    try:
        injection_assessment = assess_prompt_injection(
            context_bundle=bounded_context,
            trace_id=trace_id,
            run_id=agent_run_id,
            policy=injection_policy,
        )
        _validate_contract(injection_assessment, "prompt_injection_assessment")
        enforcement_outcome = evaluate_enforcement_outcome(
            injection_assessment,
            policy=injection_policy,
        )
    except PromptInjectionDefenseError as exc:
        raise AgentExecutionBlockedError(f"prompt injection defense failed: {exc}") from exc
    except Exception as exc:
        raise AgentExecutionBlockedError(
            f"prompt injection assessment validation failed: {exc}"
        ) from exc

    if enforcement_outcome["should_block"]:
        raise AgentExecutionBlockedError(
            f"prompt injection enforcement blocked execution: {enforcement_outcome['blocked_reason']}"
        )

    planned_steps = [deepcopy(step) for step in step_plan]

    started_at = _now_iso()
    tool_calls: List[Dict[str, Any]] = []
    model_invocations: List[Dict[str, Any]] = []
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
        elif step_type == "model":
            requested_model_id = str(step.get("requested_model_id") or "").strip()
            if not requested_model_id:
                step["status"] = STEP_STATUS_BLOCKED
                step["error"] = "execute_step_sequence: model step missing requested_model_id"
                execution_status = EXECUTION_BLOCKED
                failure_reason = step["error"]
                break
            if model_adapter is None:
                step["status"] = STEP_STATUS_BLOCKED
                step["error"] = "execute_step_sequence: model step requires model_adapter"
                execution_status = EXECUTION_BLOCKED
                failure_reason = step["error"]
                break
            input_text = str(step.get("input_text") or bounded_context.get("primary_input") or "")
            if not input_text.strip():
                step["status"] = STEP_STATUS_BLOCKED
                step["error"] = "execute_step_sequence: model step missing input_text"
                execution_status = EXECUTION_BLOCKED
                failure_reason = step["error"]
                break

            requires_structured_generation = bool(step.get("requires_structured_generation", False))
            structured_output = step.get("structured_output")
            if requires_structured_generation and not isinstance(structured_output, dict):
                step["status"] = STEP_STATUS_BLOCKED
                step["error"] = (
                    "execute_step_sequence: structured model step requires structured_output declaration "
                    "with target_schema_ref and generation_mode"
                )
                execution_status = EXECUTION_BLOCKED
                failure_reason = step["error"]
                break

            constraints = step.get("execution_constraints") or {}
            max_output_tokens = int(constraints.get("max_output_tokens", 512))
            temperature = float(constraints.get("temperature", 0.0))
            canonical_request = build_canonical_request(
                prompt_id=str(prompt_resolution["prompt_id"]),
                prompt_version=str(prompt_resolution["prompt_version"]),
                requested_model_id=requested_model_id,
                input_text=input_text,
                trace_id=trace_id,
                agent_run_id=agent_run_id,
                step_id=str(step["step_id"]),
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                structured_output=structured_output,
            )
            try:
                canonical_response = model_adapter.execute(canonical_request)
            except ModelAdapterError as exc:
                step["status"] = STEP_STATUS_FAILED
                step["error"] = f"execute_step_sequence: model adapter failure: {exc}"
                execution_status = EXECUTION_FAILED
                failure_reason = step["error"]
                break

            step["status"] = (
                STEP_STATUS_COMPLETED
                if canonical_response["response_status"] == "completed"
                else STEP_STATUS_FAILED
            )
            step["error"] = None if step["status"] == STEP_STATUS_COMPLETED else "model response failed"
            step["output_ref"] = f"model-response://{canonical_response['response_id']}"
            model_invocations.append(
                {
                    "step_id": str(step["step_id"]),
                    "request_id": canonical_request["request_id"],
                    "response_id": canonical_response["response_id"],
                    "requested_model_id": canonical_request["requested_model_id"],
                    "provider_name": canonical_response["provider_name"],
                    "provider_model_name": canonical_response["provider_model_name"],
                    "response_status": canonical_response["response_status"],
                    "finish_reason": canonical_response["finish_reason"],
                    "structured_generation_mode": canonical_response["structured_output"]["generation_mode"],
                    "structured_target_schema_ref": canonical_response["structured_output"]["target_schema_ref"],
                    "structured_enforcement_path": canonical_response["structured_output"]["enforcement_path"],
                    "structured_output_status": canonical_response["structured_output"]["status"],
                }
            )
            if step["status"] != STEP_STATUS_COMPLETED:
                execution_status = EXECUTION_FAILED
                failure_reason = step["error"] or "model step failed"
                break

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

    multi_pass_record: Optional[Dict[str, Any]] = None
    if execution_status == EXECUTION_COMPLETED:
        builder = final_output_builder or (
            lambda bundle, steps: {
                "context_id": bundle["context_id"],
                "task_type": bundle["task_type"],
                "executed_step_ids": [s["step_id"] for s in steps if s.get("status") == STEP_STATUS_COMPLETED],
            }
        )
        draft_output = builder(bounded_context, planned_steps)
        try:
            multi_pass_record = run_multi_pass_generation(
                run_id=agent_run_id,
                trace_id=trace_id,
                input_artifact=draft_output,
            )
            final_output = dict(multi_pass_record["final_output"])
            validate_final_output(final_output, final_output_schema)
        except (MultiPassGenerationError, Exception) as exc:
            execution_status = EXECUTION_FAILED
            failure_reason = f"multi_pass_generation/validate_final_output failed: {exc}"

    final_output_artifact_id = f"agent-output://{agent_run_id}"
    source_segmentation = dict(bounded_context.get("source_segmentation") or {})
    trace = {
        "agent_run_id": agent_run_id,
        "context_bundle_id": bounded_context["context_id"],
        "context_source_summary": {
            "classification_counts": dict(source_segmentation.get("classification_counts") or {}),
            "item_refs_by_class": dict(source_segmentation.get("item_refs_by_class") or {}),
            "inferred_item_refs": list(source_segmentation.get("inferred_item_refs") or []),
            "glossary_entry_refs": list(((bounded_context.get("glossary_canonicalization") or {}).get("selected_glossary_entry_ids") or [])),
            "glossary_definition_item_refs": [
                str(item.get("item_id"))
                for item in list(bounded_context.get("context_items") or [])
                if str(item.get("item_type") or "") == "glossary_definition"
            ],
            "glossary_injection_enabled": bool(((bounded_context.get("glossary_canonicalization") or {}).get("injection_enabled"))),
            "glossary_unresolved_terms": list(((bounded_context.get("glossary_canonicalization") or {}).get("unresolved_terms") or [])),
            "glossary_fail_on_missing_required": bool(((bounded_context.get("glossary_canonicalization") or {}).get("fail_on_missing_required", False)),
            ),
            "prompt_injection": {
                "assessment_id": str(injection_assessment["assessment_id"]),
                "detection_status": str(injection_assessment["detection_status"]),
                "enforcement_action": str(injection_assessment["enforcement_action"]),
                "policy_id": str((injection_assessment.get("policy") or {}).get("policy_id") or ""),
                "flagged_item_refs": sorted(
                    {
                        str(pattern.get("item_ref") or "")
                        for pattern in list(injection_assessment.get("detected_patterns") or [])
                        if str(pattern.get("item_ref") or "").strip()
                    }
                ),
                "detected_pattern_refs": [
                    str(pattern.get("pattern_ref") or "")
                    for pattern in list(injection_assessment.get("detected_patterns") or [])
                    if str(pattern.get("pattern_ref") or "").strip()
                ],
            },
        },
        "trace_id": trace_id,
        "routing_decision": {
            "routing_decision_id": str((routing_decision or {}).get("routing_decision_id") or ""),
            "policy_id": str((routing_decision or {}).get("policy_id") or ""),
            "route_key": str((routing_decision or {}).get("route_key") or ""),
            "task_class": str((routing_decision or {}).get("task_class") or ""),
            "selected_model_id": str((routing_decision or {}).get("selected_model_id") or ""),
        },
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
        "model_invocations": model_invocations,
        "intermediate_artifacts": intermediate_artifacts,
        "multi_pass_generation": {
            "record_id": str((multi_pass_record or {}).get("record_id") or ""),
            "pass_ids": [
                str(pass_item.get("pass_id") or "")
                for pass_item in list((multi_pass_record or {}).get("passes") or [])
            ],
            "pass_output_refs": [
                str(pass_item.get("output_ref") or "")
                for pass_item in list((multi_pass_record or {}).get("passes") or [])
            ],
        },
        "final_output_artifact_id": final_output_artifact_id,
        "execution_status": execution_status,
        "failure_reason": failure_reason,
        "started_at": started_at,
        "completed_at": completed_at,
    }
    return emit_agent_execution_trace(trace)

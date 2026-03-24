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
from spectrum_systems.modules.runtime.prompt_registry import (
    PromptRegistryError,
    load_prompt_alias_map,
    load_prompt_registry_entries,
)
from spectrum_systems.modules.runtime.model_adapter import CanonicalModelAdapter
from spectrum_systems.modules.runtime.routing_policy import RoutingPolicyError, load_routing_policy, resolve_routing_decision
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


class AgentGoldenPathReviewRequired(AgentGoldenPathError):
    """Typed stop signal when execution must hand off to human review."""

    def __init__(
        self,
        review_request: Dict[str, Any],
        execution_record: Dict[str, Any],
        override_decision: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__("review_required")
        self.review_request = review_request
        self.execution_record = execution_record
        self.override_decision = override_decision


class AgentGoldenPathOverrideEnforcementError(AgentGoldenPathError):
    """Typed fail-closed stop when AG-04 override enforcement fails."""

    def __init__(
        self,
        *,
        failure_type: str,
        error_message: str,
        review_request: Dict[str, Any],
        execution_record: Dict[str, Any],
        override_decision: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(error_message)
        self.failure_type = failure_type
        self.error_message = error_message
        self.review_request = review_request
        self.execution_record = execution_record
        self.override_decision = override_decision


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
    force_review_required: bool = False
    policy_review_required: bool = False
    force_indeterminate_review: bool = False
    override_decision_paths: Optional[List[Path]] = None
    require_override_decision: bool = False

    route_key: str = "meeting_minutes_default"
    prompt_registry_entry_paths: Optional[List[Path]] = None
    prompt_alias_map_path: Optional[Path] = None
    routing_policy_path: Optional[Path] = None


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


_OVERRIDE_STATUS_TO_ACTION = {
    "allow_once": "resume_once",
    "deny": "remain_blocked",
    "require_rerun": "rerun_from_context",
    "require_revision": "revise_input_then_rerun",
}

_OVERRIDE_STATUS_COMPATIBILITY = {
    "allow_once": {"control_non_allow_response", "policy_review_required", "forced_review_required"},
    "deny": {
        "control_non_allow_response",
        "policy_review_required",
        "forced_review_required",
        "indeterminate_outcome_routed_to_human",
    },
    "require_rerun": {
        "control_non_allow_response",
        "policy_review_required",
        "forced_review_required",
        "indeterminate_outcome_routed_to_human",
    },
    "require_revision": {"policy_review_required", "forced_review_required", "indeterminate_outcome_routed_to_human"},
}


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


def _build_review_artifact(
    *,
    run_id: str,
    trace_id: str,
    trigger_stage: str,
    trigger_reason: str,
    review_type: str,
    required_reviewer_role: str,
    refs: List[str],
    policy_version_id: Optional[str],
) -> Dict[str, Any]:
    identity_payload = {
        "run_id": run_id,
        "trace_id": trace_id,
        "trigger_stage": trigger_stage,
        "trigger_reason": trigger_reason,
        "review_type": review_type,
        "required_reviewer_role": required_reviewer_role,
        "source_artifact_ids": sorted(set(refs)),
        "policy_version_id": policy_version_id,
    }
    artifact = {
        "artifact_type": "hitl_review_request",
        "schema_version": "1.0.0",
        "id": deterministic_id(
            prefix="hrr",
            namespace="agent_golden_path_hitl_review",
            payload=identity_payload,
        ),
        "timestamp": _deterministic_timestamp(identity_payload),
        "status": "pending_review",
        "source_run_id": run_id,
        "trace_id": trace_id,
        "source_artifact_ids": sorted(set(refs)),
        "trigger_stage": trigger_stage,
        "trigger_reason": trigger_reason,
        "review_type": review_type,
        "required_reviewer_role": required_reviewer_role,
        "policy_version_id": policy_version_id,
    }
    _validate_contract(artifact, "hitl_review_request", stage="enforcement")
    return artifact


def _build_review_execution_record(
    *,
    run_id: str,
    trace_id: str,
    trigger_reason: str,
    refs: List[str],
) -> Dict[str, Any]:
    record = {
        "trace_id": trace_id,
        "run_id": run_id,
        "artifact_id": deterministic_id(
            prefix="cer",
            namespace="agent_golden_path_execution",
            payload={"run_id": run_id, "trace_id": trace_id, "review_reason": trigger_reason},
        ),
        "execution_status": "escalated",
        "actions_taken": [
            {
                "action_type": "agent_golden_path_review_required",
                "status": "blocked_for_review",
                "review_trigger_reason": trigger_reason,
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
        ],
        "validators_failed": [],
        "repair_actions_applied": [],
        "publication_blocked": True,
        "decision_blocked": True,
        "rerun_triggered": False,
        "escalation_triggered": True,
        "human_review_required": True,
    }
    _validate_contract(record, "control_execution_result", stage="enforcement")
    return record


def _load_override_decisions(paths: List[Path]) -> List[Dict[str, Any]]:
    decisions: List[Dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            raise AgentGoldenPathStageError(
                stage="override_enforcement",
                failure_type="override_missing",
                error_message=f"override decision not found: {path}",
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AgentGoldenPathStageError(
                stage="override_enforcement",
                failure_type="override_malformed",
                error_message=f"override decision JSON parse failed at {path}: {exc}",
            ) from exc
        _validate_contract(payload, "hitl_override_decision", stage="override_enforcement")
        decisions.append(payload)
    return decisions


def _evaluate_override_decision(
    *,
    review_request: Dict[str, Any],
    review_execution_record: Dict[str, Any],
    override_decision: Dict[str, Any],
) -> Dict[str, Any]:
    status = str(override_decision["decision_status"])
    allowed_next_action = str(override_decision["allowed_next_action"])
    expected_action = _OVERRIDE_STATUS_TO_ACTION.get(status)
    if expected_action is None:
        raise ValueError(f"unsupported decision_status: {status}")
    if allowed_next_action != expected_action:
        raise ValueError(
            f"allowed_next_action '{allowed_next_action}' is incompatible with decision_status '{status}'"
        )
    if override_decision.get("decision_scope") != "ag_runtime_review_boundary":
        raise ValueError(f"unsupported decision_scope '{override_decision.get('decision_scope')}'")
    if override_decision.get("trace_id") != review_request.get("trace_id"):
        raise ValueError("override trace_id does not match review trace_id")
    if override_decision.get("review_request_id") != review_request.get("id"):
        raise ValueError("override review_request_id does not match emitted review_request id")
    if override_decision.get("related_execution_record_id") != review_execution_record.get("artifact_id"):
        raise ValueError("override related_execution_record_id does not match emitted execution record id")
    trigger_reason = str(review_request.get("trigger_reason"))
    if trigger_reason not in _OVERRIDE_STATUS_COMPATIBILITY[status]:
        raise ValueError(
            f"decision_status '{status}' is incompatible with trigger_reason '{trigger_reason}'"
        )
    return {
        "decision_status": status,
        "allowed_next_action": allowed_next_action,
        "override_decision_id": override_decision["override_decision_id"],
    }


def _resolve_review_override(
    *,
    config: GoldenPathConfig,
    review_request: Dict[str, Any],
    review_execution_record: Dict[str, Any],
) -> Dict[str, Any]:
    raw_paths = config.override_decision_paths or []
    unique_paths = sorted({Path(p).resolve() for p in raw_paths}, key=lambda p: str(p))
    if not unique_paths:
        if config.require_override_decision:
            raise AgentGoldenPathStageError(
                stage="override_enforcement",
                failure_type="override_missing",
                error_message="review boundary requires a hitl_override_decision artifact, but none were supplied",
            )
        raise AgentGoldenPathReviewRequired(review_request, review_execution_record)

    decisions = _load_override_decisions(unique_paths)
    if len(decisions) != 1:
        raise AgentGoldenPathStageError(
            stage="override_enforcement",
            failure_type="override_ambiguous",
            error_message=f"exactly one override artifact is required, found {len(decisions)}",
        )
    override_decision = decisions[0]
    try:
        outcome = _evaluate_override_decision(
            review_request=review_request,
            review_execution_record=review_execution_record,
            override_decision=override_decision,
        )
    except ValueError as exc:
        raise AgentGoldenPathStageError(
            stage="override_enforcement",
            failure_type="override_incompatible",
            error_message=str(exc),
        ) from exc
    outcome["override_decision"] = override_decision
    return outcome


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


def _handle_review_gate(
    *,
    config: GoldenPathConfig,
    run_id: str,
    trace_id: str,
    trigger_stage: str,
    trigger_reason: str,
    review_type: str,
    required_reviewer_role: str,
    refs: List[str],
    policy_version_id: Optional[str],
) -> Dict[str, Any]:
    review_request = _build_review_artifact(
        run_id=run_id,
        trace_id=trace_id,
        trigger_stage=trigger_stage,
        trigger_reason=trigger_reason,
        review_type=review_type,
        required_reviewer_role=required_reviewer_role,
        refs=refs,
        policy_version_id=policy_version_id,
    )
    review_execution_record = _build_review_execution_record(
        run_id=run_id,
        trace_id=trace_id,
        trigger_reason=review_request["trigger_reason"],
        refs=refs + [f"hitl_review_request:{review_request['id']}"],
    )
    try:
        override_outcome = _resolve_review_override(
            config=config,
            review_request=review_request,
            review_execution_record=review_execution_record,
        )
    except AgentGoldenPathStageError as exc:
        fail_closed_record = deepcopy(review_execution_record)
        fail_closed_record["execution_status"] = "blocked"
        fail_closed_record["actions_taken"] = [
            {
                "action_type": "hitl_override_enforcement_failed",
                "status": "blocked",
                "reason": exc.failure_type,
                "message": exc.error_message,
                "review_request_id": review_request["id"],
                "artifact_references": sorted(set(refs + [f"hitl_review_request:{review_request['id']}"])),
                "timestamp": _now_iso(),
            }
        ]
        fail_closed_record["publication_blocked"] = True
        fail_closed_record["decision_blocked"] = True
        fail_closed_record["rerun_triggered"] = False
        fail_closed_record["escalation_triggered"] = True
        fail_closed_record["human_review_required"] = True
        _validate_contract(fail_closed_record, "control_execution_result", stage="override_enforcement")
        raise AgentGoldenPathOverrideEnforcementError(
            failure_type=exc.failure_type,
            error_message=exc.error_message,
            review_request=review_request,
            execution_record=fail_closed_record,
        ) from exc
    override_decision = override_outcome["override_decision"]
    status = override_outcome["decision_status"]
    if status == "allow_once":
        return {
            "should_continue": True,
            "review_request": review_request,
            "review_execution_record": review_execution_record,
            "override_decision": override_decision,
        }

    execution_status = "blocked" if status == "deny" else "repair_required"
    action_status = "blocked" if status == "deny" else "required"
    fail_closed_record = deepcopy(review_execution_record)
    fail_closed_record["execution_status"] = execution_status
    fail_closed_record["actions_taken"] = [
        {
            "action_type": "hitl_override_decision_applied",
            "status": action_status,
            "override_status": status,
            "allowed_next_action": override_outcome["allowed_next_action"],
            "override_decision_id": override_outcome["override_decision_id"],
            "review_request_id": review_request["id"],
            "artifact_references": sorted(
                set(
                    refs
                    + [
                        f"hitl_review_request:{review_request['id']}",
                        f"hitl_override_decision:{override_decision['override_decision_id']}",
                    ]
                )
            ),
            "timestamp": _now_iso(),
        }
    ]
    fail_closed_record["repair_actions_applied"] = (
        []
        if status == "deny"
        else [{"action": override_outcome["allowed_next_action"], "reason": "hitl_override_decision"}]
    )
    fail_closed_record["publication_blocked"] = True
    fail_closed_record["decision_blocked"] = True
    fail_closed_record["rerun_triggered"] = status == "require_rerun"
    fail_closed_record["escalation_triggered"] = status == "deny"
    fail_closed_record["human_review_required"] = status != "deny"
    _validate_contract(fail_closed_record, "control_execution_result", stage="override_enforcement")
    raise AgentGoldenPathReviewRequired(
        review_request=review_request,
        execution_record=fail_closed_record,
        override_decision=override_decision,
    )


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
                config={**dict(config.context_config), "trace_id": trace_id, "run_id": run_id},
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
        registry_paths = config.prompt_registry_entry_paths or [Path("contracts/examples/prompt_registry_entry.json")]
        alias_map_path = config.prompt_alias_map_path or Path("contracts/examples/prompt_alias_map.json")
        routing_policy_path = config.routing_policy_path or Path("contracts/examples/routing_policy.json")
        try:
            prompt_entries = load_prompt_registry_entries(registry_paths)
            prompt_alias_map = load_prompt_alias_map(alias_map_path)
            routing_policy = load_routing_policy(routing_policy_path)
            routing_resolution = resolve_routing_decision(
                policy=routing_policy,
                route_key=config.route_key,
                task_class=config.task_type,
                trace_id=trace_id,
                agent_run_id=run_id,
                prompt_entries=prompt_entries,
                prompt_alias_map=prompt_alias_map,
            )
            prompt_resolution = routing_resolution["prompt_resolution"]
            routing_decision = routing_resolution["routing_decision"]
        except (PromptRegistryError, RoutingPolicyError) as exc:
            raise AgentGoldenPathStageError(
                stage="agent",
                failure_type="policy_error",
                error_message=str(exc),
            ) from exc
        artifacts["routing_decision"] = routing_decision
        refs.append(f"routing_decision:{routing_decision['routing_decision_id']}")

        step_plan = generate_step_plan(
            context_bundle,
            [
                {
                    "step_id": "step-001",
                    "step_type": "model",
                    "requested_model_id": routing_decision["selected_model_id"],
                    "input_ref": f"context://{context_bundle['context_id']}",
                    "input_text": json.dumps(
                        {
                            "context_id": context_bundle["context_id"],
                            "task_type": context_bundle["task_type"],
                            "goal": "generate_structured_signal",
                        },
                        sort_keys=True,
                    ),
                    "execution_constraints": {"max_output_tokens": 256, "temperature": 0.0},
                    "requires_structured_generation": False,
                }
            ],
        )

        class _GoldenPathProvider:
            provider_name = "openai"

            def invoke(self, provider_request: Dict[str, Any]) -> Dict[str, Any]:
                return _provider_fn(provider_request)

        def _provider_fn(payload: Dict[str, Any]) -> Dict[str, Any]:
            if config.fail_agent_execution:
                raise RuntimeError("forced_agent_execution_failure")
            return {
                "model": str(payload["model"]).split(":")[-1],
                "output_text": f"structured-signal::{payload['request_id']}",
                "finish_reason": "stop",
            }

        try:
            trace = execute_step_sequence(
                agent_run_id=run_id,
                trace_id=trace_id,
                prompt_resolution=prompt_resolution,
                context_bundle=context_bundle,
                step_plan=step_plan,
                final_output_schema="eval_case",
                model_adapter=CanonicalModelAdapter(provider=_GoldenPathProvider()),
                final_output_builder=lambda bundle, steps: _build_structured_output(
                    trace_id=trace_id,
                    run_id=run_id,
                    context_bundle=bundle,
                    tool_calls=[s for s in steps if s.get("step_type") in {"tool", "model"}],
                    force_invalid=False,
                    force_eval_status=config.force_eval_status,
                ),
                routing_decision=routing_decision,
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

        if config.force_review_required:
            review_gate = _handle_review_gate(
                config=config,
                run_id=run_id,
                trace_id=trace_id,
                trigger_stage="agent",
                trigger_reason="forced_review_required",
                review_type="manual_test_review",
                required_reviewer_role="governance_reviewer",
                refs=refs,
                policy_version_id="ag03-policy-v1",
            )
            artifacts["hitl_review_request"] = review_gate["review_request"]
            artifacts["hitl_override_decision"] = review_gate["override_decision"]
            refs.append(f"hitl_review_request:{review_gate['review_request']['id']}")
            refs.append(f"hitl_override_decision:{review_gate['override_decision']['override_decision_id']}")

        if config.policy_review_required:
            review_gate = _handle_review_gate(
                config=config,
                run_id=run_id,
                trace_id=trace_id,
                trigger_stage="agent",
                trigger_reason="policy_review_required",
                review_type="policy_exception_review",
                required_reviewer_role="governance_reviewer",
                refs=refs,
                policy_version_id="ag03-policy-v1",
            )
            artifacts["hitl_review_request"] = review_gate["review_request"]
            artifacts["hitl_override_decision"] = review_gate["override_decision"]
            refs.append(f"hitl_review_request:{review_gate['review_request']['id']}")
            refs.append(f"hitl_override_decision:{review_gate['override_decision']['override_decision_id']}")

        indeterminate_count = int(eval_summary.get("indeterminate_failure_count", 0))
        if config.force_indeterminate_review:
            indeterminate_count = max(1, indeterminate_count)
        if indeterminate_count > 0:
            review_gate = _handle_review_gate(
                config=config,
                run_id=run_id,
                trace_id=trace_id,
                trigger_stage="eval",
                trigger_reason="indeterminate_outcome_routed_to_human",
                review_type="confidence_review",
                required_reviewer_role="governance_reviewer",
                refs=refs,
                policy_version_id="ag03-policy-v1",
            )
            artifacts["hitl_review_request"] = review_gate["review_request"]
            artifacts["hitl_override_decision"] = review_gate["override_decision"]
            refs.append(f"hitl_review_request:{review_gate['review_request']['id']}")
            refs.append(f"hitl_override_decision:{review_gate['override_decision']['override_decision_id']}")

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

        system_response = str(decision.get("system_response", "block"))
        if system_response != "allow":
            review_gate = _handle_review_gate(
                config=config,
                run_id=run_id,
                trace_id=trace_id,
                trigger_stage="control",
                trigger_reason="control_non_allow_response",
                review_type="control_escalation_review",
                required_reviewer_role="control_authority_reviewer",
                refs=refs,
                policy_version_id="ag03-policy-v1",
            )
            artifacts["hitl_review_request"] = review_gate["review_request"]
            artifacts["hitl_override_decision"] = review_gate["override_decision"]
            refs.append(f"hitl_review_request:{review_gate['review_request']['id']}")
            refs.append(f"hitl_override_decision:{review_gate['override_decision']['override_decision_id']}")

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

    except AgentGoldenPathOverrideEnforcementError as exc:
        artifacts["hitl_review_request"] = exc.review_request
        artifacts["final_execution_record"] = exc.execution_record
        if exc.override_decision is not None:
            artifacts["hitl_override_decision"] = exc.override_decision
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
    except AgentGoldenPathReviewRequired as review_required:
        artifacts["hitl_review_request"] = review_required.review_request
        artifacts["final_execution_record"] = review_required.execution_record
        if review_required.override_decision is not None:
            artifacts["hitl_override_decision"] = review_required.override_decision

    output_paths = {
        "context_bundle": config.output_dir / "context_bundle.json",
        "routing_decision": config.output_dir / "routing_decision.json",
        "agent_execution_trace": config.output_dir / "agent_execution_trace.json",
        "structured_output": config.output_dir / "structured_output.json",
        "eval_result": config.output_dir / "eval_result.json",
        "eval_summary": config.output_dir / "eval_summary.json",
        "control_decision": config.output_dir / "control_decision.json",
        "enforcement": config.output_dir / "enforcement.json",
        "final_execution_record": config.output_dir / "final_execution_record.json",
        "failure_artifact": config.output_dir / "failure_artifact.json",
        "hitl_review_request": config.output_dir / "hitl_review_request.json",
        "hitl_override_decision": config.output_dir / "hitl_override_decision.json",
    }
    for key, payload in artifacts.items():
        _emit_json(output_paths[key], payload)

    return artifacts

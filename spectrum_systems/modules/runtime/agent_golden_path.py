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

from spectrum_systems.contracts import load_example, load_schema
from spectrum_systems.modules.agents.agent_executor import execute_step_sequence, generate_step_plan
from spectrum_systems.modules.ai_workflow.context_assembly import build_context_bundle
from spectrum_systems.modules.evaluation.eval_engine import compute_eval_summary, run_eval_case
from spectrum_systems.modules.runtime.control_loop import (
    build_trace_context_from_replay_artifact,
    run_control_loop,
)
from spectrum_systems.modules.runtime.enforcement_engine import enforce_control_decision
from spectrum_systems.modules.runtime.context_admission import run_context_admission
from spectrum_systems.modules.runtime.evaluation_enforcement_bridge import build_enforcement_action
from spectrum_systems.modules.runtime.trace_store import persist_trace
from spectrum_systems.modules.governance.done_certification import DoneCertificationError
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


_ARTIFACT_ID_KEYS: Dict[str, str] = {
    "context_bundle": "context_id",
    "context_validation_result": "validation_id",
    "context_admission_decision": "admission_decision_id",
    "routing_decision": "routing_decision_id",
    "agent_execution_trace": "agent_run_id",
    "structured_output": "eval_case_id",
    "eval_result": "eval_case_id",
    "eval_summary": "eval_run_id",
    "replay_result": "replay_id",
    "control_decision": "decision_id",
    "enforcement": "enforcement_result_id",
    "final_execution_record": "artifact_id",
    "failure_artifact": "id",
    "hitl_review_request": "id",
    "hitl_override_decision": "override_decision_id",
    "meeting_minutes_record": "artifact_id",
    "grounding_factcheck_eval": "eval_id",
    "evaluation_enforcement_action": "action_id",
    "replay_execution_record": "replay_id",
    "control_loop_certification_pack": "certification_id",
    "done_certification_record": "certification_id",
    "done_certification_error": "certification_error_id",
    "observability_record": "record_id",
    "observability_metrics": "artifact_id",
    "persisted_trace": "trace_id",
    "artifact_lineage": "artifact_id",
}


_MAX_OVERRIDE_VALIDITY_SECONDS = 86_400


def _parse_iso8601(value: str, *, field_name: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO 8601 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone information")
    return parsed.astimezone(timezone.utc)


def _validate_override_expiry_window(
    *,
    override_decision: Dict[str, Any],
    enforcement_now: datetime,
) -> None:
    issued_at = _parse_iso8601(str(override_decision.get("issued_at", "")), field_name="issued_at")
    expires_at = _parse_iso8601(str(override_decision.get("expires_at", "")), field_name="expires_at")
    max_validity_seconds = int(override_decision.get("max_validity_seconds", 0))
    if max_validity_seconds < 1:
        raise ValueError("max_validity_seconds must be >= 1")
    if max_validity_seconds > _MAX_OVERRIDE_VALIDITY_SECONDS:
        raise ValueError(
            f"max_validity_seconds exceeds policy bound ({_MAX_OVERRIDE_VALIDITY_SECONDS})"
        )
    window_seconds = int((expires_at - issued_at).total_seconds())
    if window_seconds < 1:
        raise ValueError("expires_at must be after issued_at")
    if window_seconds > max_validity_seconds:
        raise ValueError("override validity window exceeds declared max_validity_seconds")
    if enforcement_now > expires_at:
        raise ValueError("override decision expired at enforcement boundary")


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


def _build_replay_result_for_control(
    *,
    eval_summary: Dict[str, Any],
    run_id: str,
    trace_id: str,
    force_control_block: bool,
) -> Dict[str, Any]:
    replay = deepcopy(load_example("replay_result"))
    replay["replay_id"] = f"RPL-{run_id}"
    replay["original_run_id"] = run_id
    replay["replay_run_id"] = run_id
    replay["trace_id"] = trace_id
    replay["timestamp"] = str(eval_summary.get("created_at") or _deterministic_timestamp({"run_id": run_id, "trace_id": trace_id}))
    replay["input_artifact_reference"] = f"eval_summary:{run_id}"

    pass_rate = float(eval_summary.get("pass_rate", 0.0))
    drift_rate = float(eval_summary.get("drift_rate", 1.0))
    reproducibility = float(eval_summary.get("reproducibility_score", 0.0))
    if force_control_block:
        pass_rate = 0.0
        drift_rate = 1.0
        reproducibility = 0.0
    consistency_status = "mismatch" if reproducibility < 0.8 else "match"

    replay["consistency_status"] = consistency_status
    replay["drift_detected"] = consistency_status == "mismatch"
    replay["failure_reason"] = None
    replay["provenance"]["trace_id"] = trace_id
    replay["provenance"]["source_artifact_id"] = run_id

    replay["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay["observability_metrics"]["metrics"]["replay_success_rate"] = pass_rate
    replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = drift_rate

    replay["error_budget_status"]["trace_refs"]["trace_id"] = trace_id
    replay["error_budget_status"]["observability_metrics_id"] = replay["observability_metrics"]["artifact_id"]
    objectives = replay["error_budget_status"].get("objectives", [])
    triggered_conditions = []
    objective_statuses = []
    for objective in objectives:
        if not isinstance(objective, dict):
            continue
        metric_name = objective.get("metric_name")
        target_value = float(objective.get("target_value", 0.0))
        if metric_name == "replay_success_rate":
            observed_value = pass_rate
            consumed_error = max(0.0, target_value - observed_value)
        elif metric_name == "drift_exceed_threshold_rate":
            observed_value = drift_rate
            consumed_error = max(0.0, observed_value - target_value)
        else:
            continue
        allowed_error = float(objective.get("allowed_error", max(0.0, 1.0 - target_value)))
        consumption_ratio = 1.0 if allowed_error <= 0 else min(1.0, consumed_error / allowed_error)
        if consumption_ratio >= 1.0:
            objective_status = "exhausted"
        elif consumption_ratio >= 0.8:
            objective_status = "warning"
        else:
            objective_status = "healthy"
        objective["observed_value"] = observed_value
        objective["consumed_error"] = consumed_error
        objective["remaining_error"] = max(0.0, allowed_error - consumed_error)
        objective["consumption_ratio"] = consumption_ratio
        objective["status"] = objective_status
        objective_statuses.append(objective_status)
        if objective_status in {"warning", "exhausted", "invalid"}:
            triggered_conditions.append(
                {
                    "metric_name": metric_name,
                    "status": objective_status,
                    "consumption_ratio": consumption_ratio,
                }
            )

    if "exhausted" in objective_statuses:
        aggregate_budget_status = "exhausted"
    elif "warning" in objective_statuses:
        aggregate_budget_status = "warning"
    else:
        aggregate_budget_status = "healthy"
    replay["error_budget_status"]["budget_status"] = aggregate_budget_status
    replay["error_budget_status"]["highest_severity"] = aggregate_budget_status
    replay["error_budget_status"]["triggered_conditions"] = triggered_conditions
    replay["error_budget_status"]["reasons"] = [
        "error_budget_derived_from_replay_metrics"
    ] if triggered_conditions else []

    if force_control_block and aggregate_budget_status != "exhausted":
        replay["error_budget_status"]["budget_status"] = "exhausted"
        replay["error_budget_status"]["highest_severity"] = "exhausted"
        replay["error_budget_status"]["triggered_conditions"] = [
            {
                "metric_name": "replay_success_rate",
                "status": "exhausted",
                "consumption_ratio": 1.0,
            }
        ]
        replay["error_budget_status"]["reasons"] = ["forced_control_block_budget_exhausted"]
    if not isinstance(replay.get("error_budget_status"), dict):
        raise AgentGoldenPathError("replay_result for control must include error_budget_status")
    return replay


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
    _validate_override_expiry_window(
        override_decision=override_decision,
        enforcement_now=datetime.now(timezone.utc),
    )
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
    upstream_refs: List[str],
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
        "run_id": run_id,
        "trace_id": trace_id,
        "eval_case_id": eval_case_id,
        "input_artifact_refs": sorted(set(upstream_refs)),
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


def _artifact_ref(artifact_type: str, artifact_id: str) -> str:
    return f"{artifact_type}:{artifact_id}"


def _artifact_id(artifacts: Dict[str, Dict[str, Any]], key: str) -> Optional[str]:
    payload = artifacts.get(key)
    if not isinstance(payload, dict):
        return None
    if key == "persisted_trace":
        trace_payload = payload.get("trace")
        if isinstance(trace_payload, dict):
            value = trace_payload.get("trace_id")
            if isinstance(value, str) and value:
                return value
        return None
    id_key = _ARTIFACT_ID_KEYS.get(key)
    if not id_key:
        return None
    value = payload.get(id_key)
    if isinstance(value, str) and value:
        return value
    return None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AgentGoldenPathStageError(stage="enforcement", failure_type="validation_error", error_message=message)


def _extract_artifact_identity(name: str, payload: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    if name in {"context_bundle", "context_validation_result", "context_admission_decision"}:
        trace = payload.get("trace")
        if isinstance(trace, dict):
            return trace.get("run_id"), trace.get("trace_id")
        return None, None
    if name == "routing_decision":
        trace = payload.get("trace")
        if isinstance(trace, dict):
            return trace.get("agent_run_id"), trace.get("trace_id")
        return None, None
    if name == "hitl_review_request":
        return payload.get("source_run_id"), payload.get("trace_id")
    if name in {"grounding_factcheck_eval"}:
        return payload.get("run_id"), payload.get("trace_id")
    if name in {"replay_execution_record"}:
        return payload.get("run_id"), payload.get("trace_id")
    if name in {"meeting_minutes_record"}:
        return payload.get("run_id"), payload.get("trace_id")
    if name == "agent_execution_trace":
        return payload.get("agent_run_id"), payload.get("trace_id")
    if name == "eval_summary":
        return payload.get("eval_run_id"), payload.get("trace_id")
    if name == "replay_result":
        return payload.get("replay_run_id"), payload.get("trace_id")
    if name == "done_certification_record":
        return payload.get("run_id"), payload.get("trace_id")
    return payload.get("run_id"), payload.get("trace_id")


def _validate_trace_and_lineage(artifacts: Dict[str, Dict[str, Any]], *, trace_id: str, run_id: str) -> None:
    """Fail-closed trace/linkage checks for emitted governed artifacts."""
    strict_run_identity_artifacts = {
        "context_bundle",
        "context_validation_result",
        "context_admission_decision",
        "routing_decision",
        "agent_execution_trace",
        "eval_summary",
        "replay_result",
        "control_decision",
        "enforcement",
        "final_execution_record",
        "failure_artifact",
        "hitl_review_request",
        "meeting_minutes_record",
        "grounding_factcheck_eval",
        "replay_execution_record",
        "control_loop_certification_pack",
        "done_certification_record",
        "done_certification_error",
        "observability_record",
        "artifact_lineage",
    }
    for name, payload in artifacts.items():
        if not isinstance(payload, dict):
            continue
        if name == "observability_metrics":
            trace_refs = payload.get("trace_refs")
            _require(
                isinstance(trace_refs, dict) and trace_refs.get("trace_id") == trace_id,
                "observability_metrics missing canonical trace_id linkage",
            )
            continue
        if name == "persisted_trace":
            trace_payload = payload.get("trace")
            _require(isinstance(trace_payload, dict), "persisted_trace missing trace payload")
            _require(trace_payload.get("trace_id") == trace_id, "persisted_trace missing canonical trace_id linkage")
            context = trace_payload.get("context")
            _require(isinstance(context, dict) and context.get("run_id") == run_id, "persisted_trace missing canonical run_id linkage")
            continue
        if name == "evaluation_enforcement_action":
            _require(
                payload.get("decision_id") == artifacts.get("control_decision", {}).get("decision_id"),
                "evaluation_enforcement_action missing canonical decision linkage",
            )
            continue
        artifact_run_id, artifact_trace_id = _extract_artifact_identity(name, payload)
        _require(
            isinstance(artifact_trace_id, str) and artifact_trace_id,
            f"{name} missing canonical trace_id linkage",
        )
        if name in strict_run_identity_artifacts:
            _require(
                isinstance(artifact_run_id, str) and artifact_run_id,
                f"{name} missing canonical run_id linkage",
            )
            _require(artifact_run_id == run_id, f"{name} run_id mismatch from canonical execution context")
        _require(artifact_trace_id == trace_id, f"{name} trace_id mismatch from canonical execution context")

        if name == "agent_execution_trace":
            _require(payload.get("agent_run_id") == run_id, "agent_execution_trace missing canonical agent_run_id linkage")

    eval_summary = artifacts.get("eval_summary")
    if isinstance(eval_summary, dict):
        _require(eval_summary.get("eval_run_id") == run_id, "eval_summary.eval_run_id must match canonical run_id")
    control = artifacts.get("control_decision")
    if isinstance(control, dict):
        _require(control.get("run_id") == run_id, "control_decision.run_id must match canonical run_id")
    enforcement = artifacts.get("enforcement")
    if isinstance(enforcement, dict):
        _require(enforcement.get("run_id") == run_id, "enforcement.run_id must match canonical run_id")
    execution = artifacts.get("final_execution_record")
    if isinstance(execution, dict):
        _require(execution.get("run_id") == run_id, "final_execution_record.run_id must match canonical run_id")

    context_id = _artifact_id(artifacts, "context_bundle")
    validation_id = _artifact_id(artifacts, "context_validation_result")
    admission_id = _artifact_id(artifacts, "context_admission_decision")
    routing_id = _artifact_id(artifacts, "routing_decision")
    agent_run_id = _artifact_id(artifacts, "agent_execution_trace")
    eval_case_id = _artifact_id(artifacts, "structured_output")
    eval_run_id = _artifact_id(artifacts, "eval_summary")
    replay_id = _artifact_id(artifacts, "replay_result")
    decision_id = _artifact_id(artifacts, "control_decision")

    if isinstance(artifacts.get("context_validation_result"), dict):
        _require(artifacts["context_validation_result"].get("context_bundle_id") == context_id, "context_validation_result must reference context_bundle parent")
    if isinstance(artifacts.get("context_admission_decision"), dict):
        _require(artifacts["context_admission_decision"].get("context_bundle_id") == context_id, "context_admission_decision must reference context_bundle parent")
        _require(artifacts["context_admission_decision"].get("validation_ref") == validation_id, "context_admission_decision must reference context_validation_result parent")
    if isinstance(artifacts.get("routing_decision"), dict):
        refs = set(artifacts["routing_decision"].get("related_artifact_refs") or [])
        _require(_artifact_ref("context_bundle", context_id or "") in refs, "routing_decision missing context_bundle lineage ref")
        _require(_artifact_ref("context_validation_result", validation_id or "") in refs, "routing_decision missing context_validation_result lineage ref")
        _require(_artifact_ref("context_admission_decision", admission_id or "") in refs, "routing_decision missing context_admission_decision lineage ref")
    if isinstance(artifacts.get("structured_output"), dict):
        refs = set(artifacts["structured_output"].get("input_artifact_refs") or [])
        required_refs = {
            _artifact_ref("context_bundle", context_id or ""),
            _artifact_ref("routing_decision", routing_id or ""),
            _artifact_ref("context_admission_decision", admission_id or ""),
            _artifact_ref("agent_execution_trace", agent_run_id or ""),
        }
        _require(required_refs.issubset(refs), "eval_case missing required upstream lineage refs")
    if isinstance(artifacts.get("eval_result"), dict):
        refs = set(artifacts["eval_result"].get("provenance_refs") or [])
        _require(_artifact_ref("eval_case", eval_case_id or "") in refs, "eval_result missing eval_case lineage ref")
    if isinstance(artifacts.get("replay_result"), dict):
        _require(artifacts["replay_result"].get("trace_id") == trace_id, "replay_result missing canonical trace_id linkage")
        _require(artifacts["replay_result"].get("replay_run_id") == run_id, "replay_result.replay_run_id must match canonical run_id")
    if isinstance(artifacts.get("control_decision"), dict):
        in_ref = artifacts["control_decision"].get("input_signal_reference", {})
        expected_source = replay_id or eval_run_id
        _require(in_ref.get("source_artifact_id") == expected_source, "control_decision must reference replay_result upstream artifact")
    if isinstance(artifacts.get("enforcement"), dict):
        _require(artifacts["enforcement"].get("input_decision_reference") == decision_id, "enforcement must reference control_decision upstream artifact")
    artifact_lineage = artifacts.get("artifact_lineage")
    if isinstance(artifact_lineage, dict):
        nodes = artifact_lineage.get("lineage_nodes")
        edges = artifact_lineage.get("lineage_edges")
        _require(isinstance(nodes, list) and nodes, "artifact_lineage missing lineage_nodes graph")
        _require(isinstance(edges, list), "artifact_lineage missing lineage_edges graph")
        node_ids = {
            str(node.get("artifact_id"))
            for node in nodes
            if isinstance(node, dict) and isinstance(node.get("artifact_id"), str)
        }
        for artifact_name in artifacts:
            payload = artifacts[artifact_name]
            if not isinstance(payload, dict):
                continue
            aid = _artifact_id(artifacts, artifact_name)
            _require(isinstance(aid, str) and aid, f"{artifact_name} missing artifact id for lineage graph")
            _require(aid in node_ids, f"artifact_lineage missing node for {artifact_name}")


def _build_mvp_extension_artifacts(
    *,
    artifacts: Dict[str, Dict[str, Any]],
    run_id: str,
    trace_id: str,
    context_bundle: Dict[str, Any],
    trace_store_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    """Build MVP-01 required governed artifacts tied to the same run/trace."""
    meeting_minutes = deepcopy(load_example("meeting_minutes_record"))
    meeting_minutes["run_id"] = run_id
    meeting_minutes["trace_id"] = trace_id
    record_digest = hashlib.sha256(f"{run_id}:{trace_id}:meeting_record".encode("utf-8")).hexdigest()[:16].upper()
    meeting_minutes["record_id"] = f"REC-{record_digest}"
    minutes_digest = hashlib.sha256(f"{run_id}:{trace_id}:meeting_minutes".encode("utf-8")).hexdigest()[:16].upper()
    meeting_minutes["artifact_id"] = f"MMR-{minutes_digest}"

    grounding_eval = deepcopy(load_example("grounding_factcheck_eval"))
    grounding_eval["run_id"] = run_id
    grounding_eval["trace_id"] = trace_id
    grounding_eval["eval_id"] = deterministic_id(
        prefix="gfe",
        namespace="mvp01_grounding_factcheck_eval",
        payload={"run_id": run_id, "trace_id": trace_id, "source_artifact_id": meeting_minutes["artifact_id"]},
    )
    grounding_eval["source_artifact_id"] = meeting_minutes["artifact_id"]
    grounding_eval["trace_linkage"]["run_id"] = run_id
    grounding_eval["trace_linkage"]["trace_id"] = trace_id

    enforcement_action = build_enforcement_action(
        decision_id=artifacts["control_decision"]["decision_id"],
        summary_id=artifacts["eval_summary"]["eval_run_id"],
        system_response="allow" if artifacts["enforcement"].get("final_status") == "allow" else "block",
        enforcement_scope="pipeline_change",
        reasons=[f"derived_from_enforcement_result:{artifacts['enforcement']['enforcement_result_id']}"],
        required_human_actions=[],
        allowed_to_proceed=artifacts["enforcement"].get("final_status") == "allow",
        certification_gate={
            "artifact_reference": "none",
            "certification_decision": "not_applicable",
            "certification_status": "not_applicable",
            "block_reason": None,
        },
        action_id=deterministic_id(prefix="eea", namespace="mvp01_eval_enforcement_action", payload={"run_id": run_id, "trace_id": trace_id}),
    )

    replay_execution_record = {
        "replay_id": deterministic_id(prefix="rpr", namespace="mvp01_replay_execution_record", payload={"run_id": run_id, "trace_id": trace_id}),
        "run_id": run_id,
        "trace_id": trace_id,
        "original_run_id": run_id,
        "replay_run_id": run_id,
        "original_trace_id": trace_id,
        "replay_trace_id": trace_id,
        "timestamp": _now_iso(),
        "replay_status": "success" if artifacts["replay_result"]["consistency_status"] == "match" else "failed",
        "consistency_check_passed": artifacts["replay_result"]["consistency_status"] == "match",
        "compared_artifacts": ["evaluation_control_decision", "enforcement_result", "eval_summary"],
        "reasons": [],
    }

    certification_pack = deepcopy(load_example("control_loop_certification_pack"))
    certification_pack["run_id"] = run_id
    certification_pack["trace_id"] = trace_id
    certification_pack["certification_id"] = deterministic_id(prefix="clc", namespace="mvp01_control_loop_cert_pack", payload={"run_id": run_id, "trace_id": trace_id})
    certification_pack["decision"] = "pass" if artifacts["enforcement"].get("final_status") == "allow" else "fail"
    certification_pack["certification_status"] = "certified" if certification_pack["decision"] == "pass" else "blocked"
    certification_pack["provenance_trace_refs"]["trace_refs"] = [trace_id]
    certification_pack["scenario_summary"]["chaos_run_id"] = replay_execution_record["replay_id"]

    done_certification = deepcopy(load_example("done_certification_record"))
    done_certification_error = None
    try:
        done_certification["certification_id"] = hashlib.sha256(f"{run_id}:{trace_id}:done_certification".encode("utf-8")).hexdigest()
        done_certification["run_id"] = run_id
        done_certification["trace_id"] = trace_id
        done_certification["input_refs"]["replay_result_ref"] = f"replay_result:{artifacts['replay_result']['replay_id']}"
        done_certification["input_refs"]["certification_pack_ref"] = f"control_loop_certification_pack:{certification_pack['certification_id']}"
        done_certification["input_refs"]["policy_ref"] = f"evaluation_control_decision:{artifacts['control_decision']['decision_id']}"
        done_certification["final_status"] = "PASSED" if certification_pack["decision"] == "pass" else "FAILED"
        done_certification["system_response"] = "allow" if done_certification["final_status"] == "PASSED" else "block"
        if done_certification["final_status"] != "PASSED":
            raise DoneCertificationError("MVP-01 certification blocked by non-allow enforcement status")
    except DoneCertificationError as exc:
        done_certification_error = deepcopy(load_example("done_certification_error"))
        done_certification_error["certification_error_id"] = deterministic_id(
            prefix="dce",
            namespace="mvp01_done_certification_error",
            payload={"run_id": run_id, "trace_id": trace_id, "message": str(exc)},
        )
        done_certification_error["run_id"] = run_id
        done_certification_error["trace_id"] = trace_id
        done_certification_error["message"] = str(exc)
        done_certification_error["input_refs"] = {
            "run_id": run_id,
            "trace_id": trace_id,
            "control_decision_id": artifacts["control_decision"]["decision_id"],
        }

    observability_record = {
        "record_id": deterministic_id(prefix="obr", namespace="mvp01_observability_record", payload={"run_id": run_id, "trace_id": trace_id}),
        "run_id": run_id,
        "trace_id": trace_id,
        "timestamp": _now_iso(),
        "context": {"artifact_id": meeting_minutes["artifact_id"], "artifact_type": "meeting_minutes_record", "pipeline_stage": "interpret", "case_id": run_id},
        "pass_info": {"pass_id": run_id, "pass_type": "meeting_minutes"},
        "metrics": {"structural_score": 1.0, "semantic_score": 1.0, "grounding_score": 1.0, "latency_ms": 1},
        "flags": {"schema_valid": True, "grounding_passed": True, "regression_passed": True, "human_disagrees": False},
        "error_summary": {"error_types": [], "failure_count": 0},
    }

    observability_metrics = deepcopy(artifacts["replay_result"]["observability_metrics"])
    observability_metrics["trace_refs"]["trace_id"] = trace_id

    trace_payload = {
        "trace_id": trace_id,
        "root_span_id": None,
        "spans": [],
        "artifacts": [
            {"artifact_id": meeting_minutes["artifact_id"], "artifact_type": "meeting_minutes_record", "attached_at": _now_iso(), "parent_span_id": None},
            {"artifact_id": artifacts["control_decision"]["decision_id"], "artifact_type": "evaluation_control_decision", "attached_at": _now_iso(), "parent_span_id": None},
            {"artifact_id": artifacts["enforcement"]["enforcement_result_id"], "artifact_type": "enforcement_result", "attached_at": _now_iso(), "parent_span_id": None},
        ],
        "start_time": _now_iso(),
        "end_time": _now_iso(),
        "context": {"run_id": run_id, "task_type": "meeting_minutes"},
        "schema_version": "1.0.0",
    }
    persisted_storage_path = persist_trace(trace_payload, base_dir=trace_store_dir)
    persisted_trace = {"envelope_version": "1.0.0", "persisted_at": _now_iso(), "storage_path": persisted_storage_path, "trace": trace_payload}

    lineage_nodes: List[Dict[str, Any]] = []
    for artifact_name, payload in artifacts.items():
        if not isinstance(payload, dict):
            continue
        artifact_id = _artifact_id(artifacts, artifact_name)
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        lineage_nodes.append(
            {
                "artifact_key": artifact_name,
                "artifact_id": artifact_id,
                "artifact_type": str(payload.get("artifact_type") or artifact_name),
                "run_id": run_id,
                "trace_id": trace_id,
            }
        )
    extension_ids = {
        "meeting_minutes_record": meeting_minutes["artifact_id"],
        "grounding_factcheck_eval": grounding_eval["eval_id"],
        "evaluation_enforcement_action": enforcement_action["action_id"],
        "replay_execution_record": replay_execution_record["replay_id"],
        "control_loop_certification_pack": certification_pack["certification_id"],
        "done_certification_record": done_certification["certification_id"],
        "observability_record": observability_record["record_id"],
        "observability_metrics": observability_metrics["artifact_id"],
        "persisted_trace": trace_payload["trace_id"],
    }
    if done_certification_error is not None:
        extension_ids["done_certification_error"] = done_certification_error["certification_error_id"]
    for artifact_name, artifact_id in extension_ids.items():
        lineage_nodes.append(
            {
                "artifact_key": artifact_name,
                "artifact_id": artifact_id,
                "artifact_type": artifact_name,
                "run_id": run_id,
                "trace_id": trace_id,
            }
        )

    lineage_edges = [
        {"parent_artifact_id": context_bundle["context_id"], "child_artifact_id": artifacts["context_validation_result"]["validation_id"]},
        {"parent_artifact_id": context_bundle["context_id"], "child_artifact_id": artifacts["context_admission_decision"]["admission_decision_id"]},
        {"parent_artifact_id": context_bundle["context_id"], "child_artifact_id": artifacts["routing_decision"]["routing_decision_id"]},
        {"parent_artifact_id": context_bundle["context_id"], "child_artifact_id": artifacts["agent_execution_trace"]["agent_run_id"]},
        {"parent_artifact_id": artifacts["agent_execution_trace"]["agent_run_id"], "child_artifact_id": artifacts["structured_output"]["eval_case_id"]},
        {"parent_artifact_id": artifacts["structured_output"]["eval_case_id"], "child_artifact_id": artifacts["eval_result"]["eval_case_id"]},
        {"parent_artifact_id": artifacts["eval_result"]["eval_case_id"], "child_artifact_id": artifacts["eval_summary"]["eval_run_id"]},
        {"parent_artifact_id": artifacts["eval_summary"]["eval_run_id"], "child_artifact_id": artifacts["replay_result"]["replay_id"]},
        {"parent_artifact_id": artifacts["replay_result"]["replay_id"], "child_artifact_id": artifacts["control_decision"]["decision_id"]},
        {"parent_artifact_id": artifacts["control_decision"]["decision_id"], "child_artifact_id": artifacts["enforcement"]["enforcement_result_id"]},
        {"parent_artifact_id": artifacts["enforcement"]["enforcement_result_id"], "child_artifact_id": artifacts["final_execution_record"]["artifact_id"]},
        {"parent_artifact_id": artifacts["enforcement"]["enforcement_result_id"], "child_artifact_id": meeting_minutes["artifact_id"]},
        {"parent_artifact_id": meeting_minutes["artifact_id"], "child_artifact_id": grounding_eval["eval_id"]},
        {"parent_artifact_id": artifacts["control_decision"]["decision_id"], "child_artifact_id": enforcement_action["action_id"]},
        {"parent_artifact_id": artifacts["replay_result"]["replay_id"], "child_artifact_id": replay_execution_record["replay_id"]},
        {"parent_artifact_id": replay_execution_record["replay_id"], "child_artifact_id": certification_pack["certification_id"]},
        {"parent_artifact_id": certification_pack["certification_id"], "child_artifact_id": done_certification["certification_id"]},
        {"parent_artifact_id": meeting_minutes["artifact_id"], "child_artifact_id": observability_record["record_id"]},
        {"parent_artifact_id": artifacts["replay_result"]["observability_metrics"]["artifact_id"], "child_artifact_id": observability_metrics["artifact_id"]},
        {"parent_artifact_id": meeting_minutes["artifact_id"], "child_artifact_id": trace_payload["trace_id"]},
    ]
    if done_certification_error is not None:
        lineage_edges.append(
            {"parent_artifact_id": certification_pack["certification_id"], "child_artifact_id": done_certification_error["certification_error_id"]}
        )
    lineage_depth = max((node.get("lineage_depth", 0) for node in lineage_nodes if isinstance(node, dict)), default=0) + 1
    artifact_lineage = {
        "artifact_id": deterministic_id(prefix="lin", namespace="mvp01_artifact_lineage", payload={"run_id": run_id, "trace_id": trace_id}),
        "run_id": run_id,
        "trace_id": trace_id,
        "artifact_type": "decision",
        "parent_artifact_ids": [context_bundle["context_id"], artifacts["agent_execution_trace"]["agent_run_id"]],
        "created_at": _now_iso(),
        "created_by": "agent_golden_path",
        "version": "1.0.0",
        "lineage_depth": lineage_depth,
        "root_artifact_ids": [context_bundle["context_id"]],
        "lineage_valid": True,
        "lineage_errors": [],
        "lineage_nodes": lineage_nodes,
        "lineage_edges": lineage_edges,
    }
    artifact_lineage["lineage_nodes"].append(
        {
            "artifact_key": "artifact_lineage",
            "artifact_id": artifact_lineage["artifact_id"],
            "artifact_type": "artifact_lineage",
            "run_id": run_id,
            "trace_id": trace_id,
        }
    )

    extension = {
        "meeting_minutes_record": meeting_minutes,
        "grounding_factcheck_eval": grounding_eval,
        "evaluation_enforcement_action": enforcement_action,
        "replay_execution_record": replay_execution_record,
        "control_loop_certification_pack": certification_pack,
        "done_certification_record": done_certification,
        "observability_record": observability_record,
        "observability_metrics": observability_metrics,
        "persisted_trace": persisted_trace,
        "artifact_lineage": artifact_lineage,
    }
    if done_certification_error is not None:
        extension["done_certification_error"] = done_certification_error
    return extension


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
        prefix="run",
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

        # 1.5) Context admission gate (TRUST-01 pre-execution fail-closed boundary)
        try:
            admission = run_context_admission(context_bundle=context_bundle, stage="observe")
            _validate_contract(admission["context_validation_result"], "context_validation_result", stage="context_admission")
            _validate_contract(admission["context_admission_decision"], "context_admission_decision", stage="context_admission")
        except AgentGoldenPathStageError:
            raise
        except Exception as exc:
            raise AgentGoldenPathStageError(
                stage="context_admission",
                failure_type="policy_error",
                error_message=str(exc),
            ) from exc

        artifacts["context_validation_result"] = admission["context_validation_result"]
        artifacts["context_admission_decision"] = admission["context_admission_decision"]
        refs.append(f"context_validation_result:{admission['context_validation_result']['validation_id']}")
        refs.append(f"context_admission_decision:{admission['context_admission_decision']['admission_decision_id']}")
        if admission["context_admission_decision"]["decision_status"] != "allow":
            raise AgentGoldenPathStageError(
                stage="context_admission",
                failure_type="policy_error",
                error_message="context admission blocked execution",
            )

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
        artifacts["routing_decision"]["related_artifact_refs"] = sorted(
            set(
                list(routing_decision.get("related_artifact_refs") or [])
                + [
                    f"context_bundle:{context_bundle['context_id']}",
                    f"context_validation_result:{admission['context_validation_result']['validation_id']}",
                    f"context_admission_decision:{admission['context_admission_decision']['admission_decision_id']}",
                ]
            )
        )
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
                model_adapter=CanonicalModelAdapter(
                    provider=_GoldenPathProvider(),
                    prompt_registry_entries=tuple(prompt_entries),
                ),
                final_output_builder=lambda bundle, steps: _build_structured_output(
                    trace_id=trace_id,
                    run_id=run_id,
                    context_bundle=bundle,
                    tool_calls=[s for s in steps if s.get("step_type") in {"tool", "model"}],
                    upstream_refs=[
                        f"context_bundle:{bundle['context_id']}",
                        f"routing_decision:{routing_decision['routing_decision_id']}",
                        f"context_admission_decision:{admission['context_admission_decision']['admission_decision_id']}",
                        f"agent_execution_trace:{run_id}",
                    ],
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
            upstream_refs=[
                f"context_bundle:{context_bundle['context_id']}",
                f"routing_decision:{routing_decision['routing_decision_id']}",
                f"context_admission_decision:{admission['context_admission_decision']['admission_decision_id']}",
                f"agent_execution_trace:{run_id}",
            ],
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
            eval_result["provenance_refs"] = sorted(
                set(
                    list(eval_result.get("provenance_refs") or [])
                    + [
                        f"eval_case:{structured_output['eval_case_id']}",
                        f"agent_execution_trace:{run_id}",
                        f"routing_decision:{routing_decision['routing_decision_id']}",
                    ]
                )
            )
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
            replay_result = _build_replay_result_for_control(
                eval_summary=eval_summary,
                run_id=run_id,
                trace_id=trace_id,
                force_control_block=config.force_control_block,
            )
            _validate_contract(replay_result, "replay_result", stage="control")
            artifacts["replay_result"] = replay_result
            refs.append(f"replay_result:{replay_result['replay_id']}")
            control_trace_context = build_trace_context_from_replay_artifact(
                replay_result,
                base_context={
                    "execution_id": run_id,
                    "stage": "control",
                    "runtime_environment": "agent_golden_path",
                },
            )
            control = run_control_loop(
                replay_result,
                control_trace_context,
            )
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

        final_status = str(enforcement.get("final_status", "deny"))
        continuation_allowed = final_status == "allow"
        warning_flag = final_status == "require_review"

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
                    "control_decision": final_status,
                    "artifact_references": sorted(set(refs)),
                    "timestamp": _now_iso(),
                }
            ],
            "validators_run": [
                "context_bundle",
                "context_admission",
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
        extension_artifacts = _build_mvp_extension_artifacts(
            artifacts=artifacts,
            run_id=run_id,
            trace_id=trace_id,
            context_bundle=context_bundle,
            trace_store_dir=config.output_dir / "traces",
        )
        for key, payload in extension_artifacts.items():
            schema_name = key
            if key == "meeting_minutes_record":
                schema_name = "meeting_minutes_record"
            elif key == "evaluation_enforcement_action":
                schema_name = "evaluation_enforcement_action"
            elif key == "replay_execution_record":
                schema_name = "replay_execution_record"
            elif key == "control_loop_certification_pack":
                schema_name = "control_loop_certification_pack"
            elif key == "done_certification_record":
                schema_name = "done_certification_record"
            elif key == "done_certification_error":
                schema_name = "done_certification_error"
            elif key == "persisted_trace":
                schema_name = "persisted_trace"
            elif key == "artifact_lineage":
                schema_name = "artifact_lineage"
            _validate_contract(payload, schema_name, stage="enforcement")
        artifacts.update(extension_artifacts)
        _validate_trace_and_lineage(artifacts, trace_id=trace_id, run_id=run_id)

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
        "context_validation_result": config.output_dir / "context_validation_result.json",
        "context_admission_decision": config.output_dir / "context_admission_decision.json",
        "routing_decision": config.output_dir / "routing_decision.json",
        "agent_execution_trace": config.output_dir / "agent_execution_trace.json",
        "structured_output": config.output_dir / "structured_output.json",
        "eval_result": config.output_dir / "eval_result.json",
        "eval_summary": config.output_dir / "eval_summary.json",
        "replay_result": config.output_dir / "replay_result.json",
        "control_decision": config.output_dir / "control_decision.json",
        "enforcement": config.output_dir / "enforcement.json",
        "final_execution_record": config.output_dir / "final_execution_record.json",
        "failure_artifact": config.output_dir / "failure_artifact.json",
        "hitl_review_request": config.output_dir / "hitl_review_request.json",
        "hitl_override_decision": config.output_dir / "hitl_override_decision.json",
        "meeting_minutes_record": config.output_dir / "meeting_minutes_record.json",
        "grounding_factcheck_eval": config.output_dir / "grounding_factcheck_eval.json",
        "evaluation_enforcement_action": config.output_dir / "evaluation_enforcement_action.json",
        "replay_execution_record": config.output_dir / "replay_execution_record.json",
        "control_loop_certification_pack": config.output_dir / "control_loop_certification_pack.json",
        "done_certification_record": config.output_dir / "done_certification_record.json",
        "done_certification_error": config.output_dir / "done_certification_error.json",
        "observability_record": config.output_dir / "observability_record.json",
        "observability_metrics": config.output_dir / "observability_metrics.json",
        "persisted_trace": config.output_dir / "persisted_trace.json",
        "artifact_lineage": config.output_dir / "artifact_lineage.json",
    }
    for key, payload in artifacts.items():
        _emit_json(output_paths[key], payload)

    return artifacts

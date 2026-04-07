"""Canonical permission policy evaluation and artifact emission for governed actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class PermissionGovernanceError(ValueError):
    """Raised when permission evaluation inputs/decisions are malformed."""


@dataclass(frozen=True)
class PermissionEvaluationResult:
    permission_request_record: dict[str, Any]
    permission_decision_record: dict[str, Any]
    human_checkpoint_request: dict[str, Any] | None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_non_empty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PermissionGovernanceError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_trace(trace_id: str, trace_refs: list[str] | None) -> dict[str, Any]:
    refs = sorted({ref.strip() for ref in (trace_refs or []) if isinstance(ref, str) and ref.strip()})
    return {"trace_id": _require_non_empty(trace_id, "trace_id"), "trace_refs": refs}


def evaluate_permission_decision(
    *,
    workflow_id: str,
    stage_contract: Mapping[str, Any],
    action_name: str,
    tool_name: str,
    resource_scope: str,
    request_id: str,
    trace_id: str,
    trace_refs: list[str] | None = None,
    policy_ref: str = "permission_policy:1.0.0",
) -> PermissionEvaluationResult:
    """Evaluate permissions through one canonical decision path and emit canonical artifacts."""

    contract_id = _require_non_empty(stage_contract.get("contract_id"), "stage_contract.contract_id")
    permissions = stage_contract.get("permissions")
    if not isinstance(permissions, Mapping):
        raise PermissionGovernanceError("stage_contract.permissions must be an object")

    request_record = {
        "artifact_type": "permission_request_record",
        "schema_version": "1.0.0",
        "request_id": _require_non_empty(request_id, "request_id"),
        "workflow_id": _require_non_empty(workflow_id, "workflow_id"),
        "stage_contract_id": contract_id,
        "action_name": _require_non_empty(action_name, "action_name"),
        "tool_name": _require_non_empty(tool_name, "tool_name"),
        "resource_scope": _require_non_empty(resource_scope, "resource_scope"),
        "requested_at": _utc_now(),
        "trace": _normalize_trace(trace_id, trace_refs),
        "provenance": {"producer": "permission_governance", "produced_at": _utc_now()},
    }
    validate_artifact(request_record, "permission_request_record")

    allowlist = set(str(item).strip() for item in permissions.get("tool_allowlist", []) if str(item).strip())
    write_scope = [str(item).strip() for item in permissions.get("write_scope", []) if str(item).strip()]
    requires_human_for = set(str(item).strip() for item in permissions.get("human_approval_required_for", []) if str(item).strip())

    reasons: list[str] = []
    decision = "allow"

    if tool_name not in allowlist:
        decision = "deny"
        reasons.append("TOOL_NOT_ALLOWLISTED")

    if action_name in requires_human_for:
        decision = "require_human_approval"
        reasons.append("ACTION_REQUIRES_HUMAN_APPROVAL")

    if resource_scope.startswith("write:"):
        target = resource_scope.removeprefix("write:")
        if not any(target.startswith(prefix) for prefix in write_scope):
            decision = "deny"
            reasons.append("WRITE_SCOPE_VIOLATION")

    if not reasons:
        reasons.append("TOOL_ALLOWLIST_MATCH")

    decision_record = {
        "artifact_type": "permission_decision_record",
        "schema_version": "1.0.0",
        "decision_id": f"pdr-{request_record['request_id']}",
        "request_id": request_record["request_id"],
        "workflow_id": request_record["workflow_id"],
        "stage_contract_id": contract_id,
        "action_name": request_record["action_name"],
        "tool_name": request_record["tool_name"],
        "resource_scope": request_record["resource_scope"],
        "decision": decision,
        "policy_ref": _require_non_empty(policy_ref, "policy_ref"),
        "reason_codes": sorted(set(reasons)),
        "decided_at": _utc_now(),
        "trace": _normalize_trace(trace_id, list((trace_refs or []) + [f"permission_request_record:{request_record['request_id']}"])),
        "provenance": {"producer": "permission_governance", "produced_at": _utc_now()},
    }
    validate_artifact(decision_record, "permission_decision_record")

    checkpoint: dict[str, Any] | None = None
    if decision == "require_human_approval":
        checkpoint = {
            "artifact_type": "human_checkpoint_request",
            "schema_version": "1.0.0",
            "request_id": f"hcr-{request_record['request_id']}",
            "workflow_id": request_record["workflow_id"],
            "stage_contract_id": contract_id,
            "stage_name": str(((stage_contract.get("stage") or {}).get("name")) or "unknown_stage"),
            "checkpoint_reason": "permission_policy_requires_human_approval",
            "required_reviewer_class": "governance_operator",
            "trigger_signals": ["permission_requires_human_approval"],
            "requested_at": _utc_now(),
            "trace": _normalize_trace(trace_id, decision_record["trace"]["trace_refs"]),
            "provenance": {"producer": "permission_governance", "produced_at": _utc_now()},
        }
        validate_artifact(checkpoint, "human_checkpoint_request")

    return PermissionEvaluationResult(
        permission_request_record=request_record,
        permission_decision_record=decision_record,
        human_checkpoint_request=checkpoint,
    )


def require_checkpoint_decision(
    *,
    permission_decision_record: Mapping[str, Any],
    human_checkpoint_decision: Mapping[str, Any] | None,
) -> None:
    """Enforce human decision requirement for approval-required permission outcomes."""

    decision = str(permission_decision_record.get("decision") or "")
    if decision != "require_human_approval":
        return
    if not isinstance(human_checkpoint_decision, Mapping):
        raise PermissionGovernanceError("human checkpoint decision is required for approval-required permission outcome")
    validate_artifact(dict(human_checkpoint_decision), "human_checkpoint_decision")
    decision_value = str(human_checkpoint_decision.get("decision") or "")
    if decision_value != "approve":
        raise PermissionGovernanceError(f"human checkpoint decision blocked progression: {decision_value or 'missing_decision'}")


__all__ = [
    "PermissionGovernanceError",
    "PermissionEvaluationResult",
    "evaluate_permission_decision",
    "require_checkpoint_decision",
]

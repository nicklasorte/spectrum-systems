"""Deterministic governed lifecycle state transitions for judgment policies."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from spectrum_systems.contracts import validate_artifact


class JudgmentPolicyLifecycleError(ValueError):
    """Raised when lifecycle or rollout governance is violated."""


ALLOWED_LIFECYCLE_ACTIONS = frozenset({"create_draft", "enter_canary", "promote_active", "deprecate", "rollback", "revoke"})
ALLOWED_ROLLOUT_TYPES = frozenset({"canary", "staged", "full"})
ALLOWED_ROLLOUT_STATUSES = frozenset({"planned", "active", "completed", "aborted"})


@dataclass(frozen=True)
class PromotionInputs:
    """Governed promotion gate input bundle."""

    judgment_eval_result: dict[str, Any] | None
    judgment_drift_signal: dict[str, Any] | None
    judgment_error_budget_status: dict[str, Any] | None
    judgment_calibration_result: dict[str, Any] | None = None
    remediation_readiness_statuses: list[dict[str, Any]] = None
    control_ready: bool = False


def _artifact_identity(policy: dict[str, Any]) -> tuple[str, str]:
    policy_id = str(policy.get("artifact_id") or "")
    version = str(policy.get("artifact_version") or "")
    if not policy_id or not version:
        raise JudgmentPolicyLifecycleError("policy artifact_id and artifact_version are required")
    return policy_id, version


def _status_for_action(action: str) -> str:
    mapping = {
        "create_draft": "draft",
        "enter_canary": "canary",
        "promote_active": "active",
        "deprecate": "deprecated",
        "rollback": "active",
        "revoke": "revoked",
    }
    return mapping[action]


def _canonical_reasons(reasons: list[str] | None) -> list[str]:
    normalized = sorted({reason.strip() for reason in (reasons or []) if isinstance(reason, str) and reason.strip()})
    return normalized


def _gates_dict(gates: dict[str, bool] | None) -> dict[str, bool]:
    normalized = {
        key: bool(value)
        for key, value in sorted((gates or {}).items(), key=lambda item: item[0])
        if isinstance(key, str) and key
    }
    if not normalized:
        raise JudgmentPolicyLifecycleError("required gates evaluated must be present")
    return normalized


def build_policy_rollout_record(
    *,
    artifact_id: str,
    policy_id: str,
    policy_version: str,
    rollout_type: str,
    cohort: dict[str, Any],
    expected_gates: dict[str, Any],
    rollout_status: str,
    trace: dict[str, str],
    created_at: str,
    standards_version: str,
) -> dict[str, Any]:
    if rollout_type not in ALLOWED_ROLLOUT_TYPES:
        raise JudgmentPolicyLifecycleError(f"unsupported rollout_type: {rollout_type}")
    if rollout_status not in ALLOWED_ROLLOUT_STATUSES:
        raise JudgmentPolicyLifecycleError(f"unsupported rollout_status: {rollout_status}")
    if not isinstance(cohort, dict) or not cohort:
        raise JudgmentPolicyLifecycleError("cohort definition is required")
    if not isinstance(expected_gates, dict) or not expected_gates:
        raise JudgmentPolicyLifecycleError("expected gates / thresholds are required")

    payload = {
        "artifact_type": "judgment_policy_rollout_record",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": standards_version,
        "rollout_id": artifact_id,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "rollout_type": rollout_type,
        "cohort": cohort,
        "expected_gates": expected_gates,
        "rollout_status": rollout_status,
        "trace": trace,
        "created_at": created_at,
    }
    try:
        validate_artifact(payload, "judgment_policy_rollout_record")
    except Exception as exc:  # pragma: no cover
        raise JudgmentPolicyLifecycleError(f"invalid judgment_policy_rollout_record artifact: {exc}") from exc
    return payload


def build_policy_lifecycle_record(
    *,
    artifact_id: str,
    policy_id: str,
    from_version: str,
    to_version: str,
    lifecycle_action: str,
    source_reason: dict[str, Any],
    required_gates: dict[str, bool],
    resulting_status: str,
    trace: dict[str, str],
    actor: dict[str, str],
    created_at: str,
    standards_version: str,
) -> dict[str, Any]:
    if lifecycle_action not in ALLOWED_LIFECYCLE_ACTIONS:
        raise JudgmentPolicyLifecycleError(f"unsupported lifecycle_action: {lifecycle_action}")

    payload = {
        "artifact_type": "judgment_policy_lifecycle_record",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": standards_version,
        "lifecycle_id": artifact_id,
        "policy_id": policy_id,
        "from_version": from_version,
        "to_version": to_version,
        "lifecycle_action": lifecycle_action,
        "source_reason": source_reason,
        "required_gates": required_gates,
        "resulting_status": resulting_status,
        "trace": trace,
        "actor": actor,
        "created_at": created_at,
    }
    try:
        validate_artifact(payload, "judgment_policy_lifecycle_record")
    except Exception as exc:  # pragma: no cover
        raise JudgmentPolicyLifecycleError(f"invalid judgment_policy_lifecycle_record artifact: {exc}") from exc
    return payload


def is_trace_in_canary_cohort(trace_id: str, cohort: dict[str, Any], environment: str) -> bool:
    kind = str(cohort.get("kind") or "")
    if kind == "environment":
        values = cohort.get("values")
        return isinstance(values, list) and environment in values

    if kind == "trace_bucket":
        modulo = cohort.get("modulo")
        buckets = cohort.get("buckets")
        if not isinstance(modulo, int) or modulo <= 0:
            raise JudgmentPolicyLifecycleError("trace_bucket cohort requires positive integer modulo")
        if not isinstance(buckets, list) or not buckets:
            raise JudgmentPolicyLifecycleError("trace_bucket cohort requires non-empty buckets")
        digest = sha256(trace_id.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % modulo
        return bucket in buckets

    if kind == "explicit_trace_ids":
        values = cohort.get("values")
        return isinstance(values, list) and trace_id in values

    raise JudgmentPolicyLifecycleError(f"unsupported canary cohort kind: {kind}")


def evaluate_promotion_gates(inputs: PromotionInputs) -> dict[str, bool]:
    eval_result = inputs.judgment_eval_result
    drift_signal = inputs.judgment_drift_signal
    error_budget = inputs.judgment_error_budget_status

    if not isinstance(eval_result, dict):
        raise JudgmentPolicyLifecycleError("promotion requires judgment_eval_result")
    if not isinstance(drift_signal, dict):
        raise JudgmentPolicyLifecycleError("promotion requires judgment_drift_signal")
    if not isinstance(error_budget, dict):
        raise JudgmentPolicyLifecycleError("promotion requires judgment_error_budget_status")

    evals = eval_result.get("eval_results")
    if not isinstance(evals, list) or not evals:
        raise JudgmentPolicyLifecycleError("judgment_eval_result missing eval_results")

    eval_healthy = all(bool(item.get("passed")) for item in evals if isinstance(item, dict))
    drift_healthy = not any(bool(item.get("drift_detected")) for item in drift_signal.get("group_signals", []) if isinstance(item, dict))
    error_budget_healthy = str(error_budget.get("status")) == "healthy"
    critical_remediation_clear = not any(
        not bool(item.get("closure_eligible"))
        for item in (inputs.remediation_readiness_statuses or [])
        if isinstance(item, dict)
    )
    control_ready = bool(inputs.control_ready)

    calibration_healthy = True
    calibration = inputs.judgment_calibration_result
    if isinstance(calibration, dict):
        max_ece = 0.0
        for row in calibration.get("group_metrics", []):
            if isinstance(row, dict):
                max_ece = max(max_ece, float(row.get("expected_calibration_error", 0.0)))
        calibration_healthy = max_ece < 0.1

    gates = {
        "judgment_eval_healthy": eval_healthy,
        "drift_within_bounds": drift_healthy,
        "error_budget_healthy": error_budget_healthy,
        "critical_remediation_clear": critical_remediation_clear,
        "readiness_control_checks": control_ready,
        "calibration_within_bounds": calibration_healthy,
    }
    return gates


def transition_policy(
    *,
    policy: dict[str, Any],
    lifecycle_action: str,
    trace: dict[str, str],
    actor: dict[str, str],
    created_at: str,
    standards_version: str,
    source_reason: dict[str, Any] | None = None,
    required_gates: dict[str, bool] | None = None,
    rollout_record: dict[str, Any] | None = None,
    target_policy: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if lifecycle_action not in ALLOWED_LIFECYCLE_ACTIONS:
        raise JudgmentPolicyLifecycleError(f"unsupported lifecycle_action: {lifecycle_action}")

    policy_id, from_version = _artifact_identity(policy)
    to_version = str((target_policy or policy).get("artifact_version") or from_version)

    gates = _gates_dict(required_gates)
    if lifecycle_action == "enter_canary" and not isinstance(rollout_record, dict):
        raise JudgmentPolicyLifecycleError("canary transition requires explicit rollout artifact")

    if lifecycle_action == "rollback":
        if not isinstance(target_policy, dict):
            raise JudgmentPolicyLifecycleError("rollback requires explicit target_policy")
        target_status = str(target_policy.get("status") or "")
        if target_status != "active":
            raise JudgmentPolicyLifecycleError("rollback target_policy must be active")

    next_policy = dict(policy)
    next_policy["status"] = _status_for_action(lifecycle_action)

    lifecycle_record = build_policy_lifecycle_record(
        artifact_id=f"judgment-policy-lifecycle-{policy_id}-{from_version}-to-{to_version}-{lifecycle_action}",
        policy_id=policy_id,
        from_version=from_version,
        to_version=to_version,
        lifecycle_action=lifecycle_action,
        source_reason=source_reason or {"reasons": _canonical_reasons([]), "triggering_signals": []},
        required_gates=gates,
        resulting_status=next_policy["status"],
        trace=trace,
        actor=actor,
        created_at=created_at,
        standards_version=standards_version,
    )
    return next_policy, lifecycle_record

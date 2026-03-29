"""Governed canary rollout policy evaluation for PQX scheduling/runtime changes."""

from __future__ import annotations

from spectrum_systems.contracts import validate_artifact


class PQXCanaryRolloutError(ValueError):
    """Raised when canary rollout declarations or evaluations are unsafe."""


_REQUIRED_KEYS = {
    "rollout_scope",
    "affected_bundle_ids",
    "affected_slice_ids",
    "canary_status",
    "success_criteria",
    "failure_criteria",
    "fallback_behavior",
}


def build_canary_decision_record(*, rollout_id: str, change_type: str, rollout: dict, run_id: str, trace_id: str, created_at: str) -> dict:
    missing = [key for key in sorted(_REQUIRED_KEYS) if key not in rollout]
    if missing:
        raise PQXCanaryRolloutError(f"under-specified canary rollout: missing {missing}")

    status = rollout.get("canary_status")
    if status not in {"proposed", "active", "frozen"}:
        raise PQXCanaryRolloutError("canary_status must be one of proposed|active|frozen")

    decision = "admit" if status in {"proposed", "active"} else "freeze"
    reasons = [
        "canary rollout declaration is complete",
        f"change_type={change_type}",
        f"status={status}",
    ]
    record = {
        "schema_version": "1.0.0",
        "canary_id": rollout_id,
        "change_type": change_type,
        "decision": decision,
        "rollout_scope": rollout["rollout_scope"],
        "affected_bundle_ids": list(rollout["affected_bundle_ids"]),
        "affected_slice_ids": list(rollout["affected_slice_ids"]),
        "canary_status": status,
        "success_criteria": list(rollout["success_criteria"]),
        "failure_criteria": list(rollout["failure_criteria"]),
        "fallback_behavior": rollout["fallback_behavior"],
        "frozen_paths": list(rollout.get("frozen_paths", [])),
        "reasons": reasons,
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": created_at,
    }
    try:
        validate_artifact(record, "pqx_canary_decision_record")
    except Exception as exc:  # pragma: no cover
        raise PQXCanaryRolloutError(f"invalid pqx_canary_decision_record artifact: {exc}") from exc
    return record


def build_canary_evaluation_record(*, decision_record: dict, observed_metrics: dict, created_at: str) -> dict:
    failed = [name for name, ok in observed_metrics.items() if ok is False]
    outcome = "pass" if not failed else "fail"
    frozen_paths = list(decision_record.get("frozen_paths", []))
    if outcome == "fail":
        frozen_paths = sorted(set(frozen_paths + decision_record.get("affected_bundle_ids", [])))

    record = {
        "schema_version": "1.0.0",
        "canary_id": decision_record["canary_id"],
        "decision_ref": decision_record["canary_id"],
        "evaluation_outcome": outcome,
        "observed_metrics": observed_metrics,
        "failed_criteria": failed,
        "scheduling_freeze": outcome == "fail",
        "frozen_paths": frozen_paths,
        "created_at": created_at,
    }
    try:
        validate_artifact(record, "pqx_canary_evaluation_record")
    except Exception as exc:  # pragma: no cover
        raise PQXCanaryRolloutError(f"invalid pqx_canary_evaluation_record artifact: {exc}") from exc
    return record

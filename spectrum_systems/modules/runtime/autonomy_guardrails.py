"""Deterministic governed autonomy guardrail evaluation (BATCH-A1)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class AutonomyGuardrailError(ValueError):
    """Raised when autonomy guardrail inputs cannot be evaluated safely."""


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_schema(instance: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise AutonomyGuardrailError(f"{schema_name} validation failed: {details}")


def _normalize_drift_status(drift_signals: dict[str, Any] | None) -> str:
    drift_level = str((drift_signals or {}).get("drift_level") or "").strip().lower()
    if drift_level in {"low", "none"}:
        return "within_threshold"
    if drift_level == "medium":
        return "warning"
    if drift_level == "high":
        return "threshold_exceeded"
    return "unknown"


def _normalize_review_gate_status(review_gate_status: str | None) -> str:
    status = str(review_gate_status or "").strip().lower()
    if status in {"pass", "passed", "complete", "completed"}:
        return "passed"
    if status in {"required"}:
        return "required"
    if status in {"pending", "in_progress"}:
        return "pending"
    return "unknown"


def _normalize_replay_status(replay_status: str | None) -> str:
    status = str(replay_status or "").strip().lower()
    if status in {"passed", "match", "ready", "replay_ready", "replayable"}:
        return "passed"
    if status in {"failed", "mismatch"}:
        return "failed"
    if status in {"not_required", "na", "n/a"}:
        return "not_required"
    return "unknown"


def evaluate_autonomy_guardrails(
    *,
    source_cycle_id: str,
    autonomy_policy: dict[str, Any] | None,
    control_decisions: list[dict[str, Any]],
    unresolved_critical_risks: list[str],
    drift_signals: dict[str, Any] | None,
    replay_status: str | None,
    review_gate_status: str | None,
    required_validation_carry_forward: list[str],
    continuation_depth: int,
    consecutive_warn_count: int,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    """Evaluate governed autonomy continuation permissions deterministically and fail closed."""

    if not isinstance(created_at, str) or not created_at.strip():
        raise AutonomyGuardrailError("created_at is required")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise AutonomyGuardrailError("trace_id is required")

    drift_status = _normalize_drift_status(drift_signals)
    normalized_replay_status = _normalize_replay_status(replay_status)
    normalized_review_gate_status = _normalize_review_gate_status(review_gate_status)
    latest_control_decision = str(control_decisions[-1].get("decision") if control_decisions else "unknown").strip().lower()

    reason_codes: list[str] = []
    supporting_signals = sorted(
        {
            f"control_decision={latest_control_decision or 'unknown'}",
            f"replay_status={normalized_replay_status}",
            f"review_gate_status={normalized_review_gate_status}",
            f"drift_status={drift_status}",
            f"continuation_depth={int(continuation_depth)}",
            f"consecutive_warn_count={int(consecutive_warn_count)}",
            f"unresolved_critical_risk_count={len(unresolved_critical_risks)}",
            f"required_validation_count={len(required_validation_carry_forward)}",
        }
    )

    policy_id = "AP-000000000000"
    decision = "stop"

    malformed_policy = False
    if not isinstance(autonomy_policy, dict):
        malformed_policy = True
    else:
        try:
            _validate_schema(autonomy_policy, "autonomy_policy")
            policy_id = str(autonomy_policy["autonomy_policy_id"])
        except AutonomyGuardrailError:
            malformed_policy = True

    if malformed_policy:
        reason_codes.append("malformed_autonomy_policy")
        reason_codes.append("missing_required_input")
    else:
        assert isinstance(autonomy_policy, dict)
        max_critical = int(autonomy_policy["max_unresolved_critical_risks"])
        max_warns = int(autonomy_policy["max_consecutive_warns"])
        max_depth = int(autonomy_policy["max_continuation_depth"])
        replay_failure_policy = str(autonomy_policy["replay_failure_policy"])
        missing_eval_policy = str(autonomy_policy["missing_eval_policy"])
        escalate_control_decisions = set(autonomy_policy["escalate_conditions"]["control_decisions"])
        escalate_drift_statuses = set(autonomy_policy["escalate_conditions"]["drift_statuses"])
        review_statuses = set(autonomy_policy["review_required_conditions"]["review_gate_statuses"])
        continue_allowed_control = set(autonomy_policy["continue_conditions"]["allowed_control_decisions"])
        continue_required_replay = str(autonomy_policy["continue_conditions"]["required_replay_status"])
        continue_required_review = str(autonomy_policy["continue_conditions"]["required_review_gate_status"])
        continue_required_drift = str(autonomy_policy["continue_conditions"]["required_drift_status"])

        if continuation_depth > max_depth:
            decision = "stop"
            reason_codes.append("continuation_depth_exceeded")
        elif len(unresolved_critical_risks) > max_critical:
            decision = "stop"
            reason_codes.append("critical_risk_threshold_exceeded")
        elif consecutive_warn_count > max_warns:
            decision = "stop"
            reason_codes.append("warn_threshold_exceeded")
        elif normalized_replay_status == "failed":
            if replay_failure_policy == "escalate":
                decision = "escalate"
                reason_codes.append("replay_failure_escalate")
            elif replay_failure_policy == "require_human_review":
                decision = "require_human_review"
                reason_codes.append("replay_failure_review")
            else:
                decision = "stop"
                reason_codes.append("replay_failure_stop")
        elif normalized_review_gate_status in review_statuses or required_validation_carry_forward:
            decision = "require_human_review"
            reason_codes.append("review_gate_required")
        elif latest_control_decision in escalate_control_decisions:
            decision = "escalate"
            reason_codes.append("control_decision_freeze")
        elif drift_status in escalate_drift_statuses:
            decision = "escalate"
            reason_codes.append("drift_threshold_exceeded")
        elif latest_control_decision == "unknown":
            if missing_eval_policy == "require_human_review":
                decision = "require_human_review"
            else:
                decision = "stop"
            reason_codes.append("missing_eval_input")
        elif (
            latest_control_decision in continue_allowed_control
            and normalized_replay_status == continue_required_replay
            and normalized_review_gate_status == continue_required_review
            and drift_status == continue_required_drift
        ):
            decision = "continue"
            reason_codes.append("all_continue_conditions_satisfied")
        else:
            decision = "stop"
            reason_codes.append("missing_required_input")

    decision_seed = {
        "source_cycle_id": source_cycle_id,
        "policy_id": policy_id,
        "decision": decision,
        "reason_codes": sorted(set(reason_codes)),
        "supporting_signals": supporting_signals,
        "trace_id": trace_id,
    }
    record = {
        "autonomy_decision_id": f"ADR-{_canonical_hash(decision_seed)[:12].upper()}",
        "source_cycle_id": source_cycle_id,
        "autonomy_policy_id": policy_id,
        "decision": decision,
        "reason_codes": sorted(set(reason_codes)),
        "supporting_signals": supporting_signals,
        "unresolved_critical_risk_count": len(unresolved_critical_risks),
        "consecutive_warn_count": int(consecutive_warn_count),
        "drift_status": drift_status,
        "replay_status": normalized_replay_status,
        "review_gate_status": normalized_review_gate_status,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(record, "autonomy_decision_record")
    return record


__all__ = ["AutonomyGuardrailError", "evaluate_autonomy_guardrails"]

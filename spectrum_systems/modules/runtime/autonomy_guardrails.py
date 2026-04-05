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
    system_budget_status: dict[str, Any] | None,
    continuation_depth: int,
    consecutive_warn_count: int,
    created_at: str,
    trace_id: str,
    target_module: str | None = None,
    requested_action: str | None = None,
    tpa_maturity_signal: dict[str, Any] | None = None,
    system_health_mode: str | None = None,
    override_active: bool = False,
    override_ref: str | None = None,
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
            f"system_health_mode={str(system_health_mode or 'unknown').strip().lower() or 'unknown'}",
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
        malformed_budget_signal = False
        normalized_budget_status = dict(system_budget_status or {})
        if normalized_budget_status and "artifact_type" in normalized_budget_status:
            try:
                _validate_schema(normalized_budget_status, "system_budget_status")
            except AutonomyGuardrailError:
                malformed_budget_signal = True
        escalate_control_decisions = set(autonomy_policy["escalate_conditions"]["control_decisions"])
        escalate_drift_statuses = set(autonomy_policy["escalate_conditions"]["drift_statuses"])
        review_statuses = set(autonomy_policy["review_required_conditions"]["review_gate_statuses"])
        continue_allowed_control = set(autonomy_policy["continue_conditions"]["allowed_control_decisions"])
        continue_required_replay = str(autonomy_policy["continue_conditions"]["required_replay_status"])
        continue_required_review = str(autonomy_policy["continue_conditions"]["required_review_gate_status"])
        continue_required_drift = str(autonomy_policy["continue_conditions"]["required_drift_status"])
        if target_module and requested_action and not is_autonomy_allowed(
            {
                "module": target_module,
                "action": requested_action,
                "trend": drift_signals,
                "budget": normalized_budget_status,
            },
            autonomy_policy=autonomy_policy,
        ):
            decision = "stop"
            reason_codes.append("autonomy_scope_blocked")
        elif override_active:
            decision = "require_human_review"
            reason_codes.append("human_override_active")
            if override_ref:
                supporting_signals.append(f"override_ref={override_ref}")
        elif target_module and requested_action and tpa_maturity_signal is None:
            decision = "stop"
            reason_codes.extend(["missing_required_signal:maturity", "missing_required_input"])
        elif (
            target_module
            and requested_action
            and str((tpa_maturity_signal or {}).get("maturity_level", "experimental")) not in {"stable", "critical"}
        ):
            decision = "stop"
            reason_codes.append("maturity_below_stable")
        elif target_module and requested_action and str(system_health_mode or "").strip().lower() == "critical":
            decision = "stop"
            reason_codes.append("system_health_critical")

        elif malformed_budget_signal:
            decision = "stop"
            reason_codes.append("malformed_budget_signal")
            reason_codes.append("missing_required_input")
        elif bool(normalized_budget_status.get("budget_exhausted")):
            decision = "stop"
            reason_codes.append("budget_exhausted")
        elif continuation_depth > max_depth:
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
        elif (
            str(normalized_budget_status.get("cost_budget_status", "within_budget")) == "warning"
            or str(normalized_budget_status.get("latency_budget_status", "within_budget")) == "warning"
            or str(normalized_budget_status.get("error_budget_status", "within_budget")) == "warning"
        ) and latest_control_decision in continue_allowed_control:
            decision = "require_human_review"
            reason_codes.append("budget_warning")
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
        "maturity_level": str((tpa_maturity_signal or {}).get("maturity_level") or "experimental"),
        "system_health_mode": str(system_health_mode or "unknown").strip().lower() or "unknown",
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(record, "autonomy_decision_record")
    return record


def is_autonomy_allowed(context: dict[str, Any], *, autonomy_policy: dict[str, Any]) -> bool:
    """Return True when context falls within explicit autonomy policy scope and required safety signals."""
    _validate_schema(autonomy_policy, "autonomy_policy")
    module = str(context.get("module") or "").strip()
    action = str(context.get("action") or "").strip()
    if not module or not action:
        return False

    allowed_modules = {str(item) for item in autonomy_policy.get("allowed_modules", [])}
    allowed_actions = {str(item) for item in autonomy_policy.get("allowed_actions", [])}
    prohibited_actions = {str(item) for item in autonomy_policy.get("prohibited_actions", [])}
    if module not in allowed_modules:
        return False
    if action in prohibited_actions or action not in allowed_actions:
        return False

    trend = context.get("trend") if isinstance(context.get("trend"), dict) else {}
    budget = context.get("budget") if isinstance(context.get("budget"), dict) else {}
    required_signals = {str(item) for item in autonomy_policy.get("required_signals", [])}
    signal_state = {
        "stable trend": str(trend.get("drift_level") or "").strip().lower() in {"none", "low"},
        "healthy budget": not bool(budget.get("budget_exhausted")) and str(budget.get("cost_budget_status", "within_budget")) != "warning",
        "low volatility": str(trend.get("volatility") or "").strip().lower() in {"low", "none", ""},
    }
    return all(signal_state.get(signal, False) for signal in required_signals)


def build_tpa_maturity_signal(
    *,
    module: str,
    trend_stability: float,
    regression_frequency: float,
    test_coverage: float,
    drift_signal_strength: float,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    score = (trend_stability * 0.35) + ((1.0 - regression_frequency) * 0.25) + (test_coverage * 0.25) + ((1.0 - drift_signal_strength) * 0.15)
    if score >= 0.8:
        maturity_level = "critical"
    elif score >= 0.65:
        maturity_level = "stable"
    elif score >= 0.4:
        maturity_level = "developing"
    else:
        maturity_level = "experimental"
    payload = {
        "module": module,
        "trend_stability": round(float(trend_stability), 6),
        "regression_frequency": round(float(regression_frequency), 6),
        "test_coverage": round(float(test_coverage), 6),
        "drift_signal_strength": round(float(drift_signal_strength), 6),
        "maturity_level": maturity_level,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(payload, "tpa_maturity_signal")
    return payload


def build_autonomy_audit_record(
    *,
    action_type: str,
    trigger_signal: str,
    decision_context: dict[str, Any],
    outcome: str,
    timestamp: str,
    trace_id: str,
) -> dict[str, Any]:
    seed = {
        "action_type": action_type,
        "trigger_signal": trigger_signal,
        "decision_context": decision_context,
        "outcome": outcome,
        "trace_id": trace_id,
    }
    record = {
        "audit_id": f"AUT-{_canonical_hash(seed)[:12].upper()}",
        "action_type": action_type,
        "trigger_signal": trigger_signal,
        "decision_context": decision_context,
        "outcome": outcome,
        "timestamp": timestamp,
        "trace_id": trace_id,
    }
    _validate_schema(record, "autonomy_audit_record")
    return record


def summarize_autonomy_observability(records: list[dict[str, Any]]) -> dict[str, float]:
    total = float(len(records))
    if total == 0:
        return {"autonomy_action_count": 0.0, "autonomy_success_rate": 0.0, "autonomy_failure_rate": 0.0}
    successes = sum(1 for row in records if str(row.get("outcome", "")).lower() in {"success", "continue", "allowed"})
    failures = sum(1 for row in records if str(row.get("outcome", "")).lower() in {"failure", "blocked", "stop"})
    return {
        "autonomy_action_count": total,
        "autonomy_success_rate": round(successes / total, 6),
        "autonomy_failure_rate": round(failures / total, 6),
    }


def build_unknown_state_signal(
    *,
    source_cycle_id: str,
    source_artifact_ref: str,
    unknown_class: str,
    severity: str,
    blocking: bool,
    reason_codes: list[str],
    supporting_signal_refs: list[str],
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    payload = {
        "source_cycle_id": source_cycle_id,
        "source_artifact_ref": source_artifact_ref,
        "unknown_class": unknown_class,
        "severity": severity,
        "blocking": blocking,
        "reason_codes": sorted(set(reason_codes)),
        "supporting_signal_refs": sorted(set(supporting_signal_refs)),
        "trace_id": trace_id,
    }
    signal = {
        "unknown_state_signal_id": f"USS-{_canonical_hash(payload)[:12].upper()}",
        **payload,
        "created_at": created_at,
    }
    _validate_schema(signal, "unknown_state_signal")
    return signal


def build_decision_proof_record(
    *,
    source_decision_ref: str,
    source_cycle_id: str,
    decision_type: str,
    reason_codes: list[str],
    required_inputs_present: bool,
    supporting_signal_refs: list[str],
    supporting_artifact_refs: list[str],
    replay_consistency_status: str,
    schema_validation_status: str,
    trace_validation_status: str,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    payload = {
        "source_decision_ref": source_decision_ref,
        "source_cycle_id": source_cycle_id,
        "decision_type": decision_type,
        "reason_codes": sorted(set(reason_codes)),
        "required_inputs_present": bool(required_inputs_present),
        "supporting_signal_refs": sorted(set(supporting_signal_refs)),
        "supporting_artifact_refs": sorted(set(supporting_artifact_refs)),
        "replay_consistency_status": replay_consistency_status,
        "schema_validation_status": schema_validation_status,
        "trace_validation_status": trace_validation_status,
        "trace_id": trace_id,
    }
    record = {
        "decision_proof_id": f"DPR-{_canonical_hash(payload)[:12].upper()}",
        **payload,
        "created_at": created_at,
    }
    _validate_schema(record, "decision_proof_record")
    return record


def build_allow_decision_proof(
    *,
    source_decision_ref: str,
    eval_coverage_complete: bool,
    required_evals_present: bool,
    no_blocking_policy_violations: bool,
    no_replay_mismatch: bool,
    no_schema_failure: bool,
    no_trace_failure: bool,
    no_blocking_unknown_state_signal: bool,
    supporting_signal_refs: list[str],
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    payload = {
        "source_decision_ref": source_decision_ref,
        "eval_coverage_complete": bool(eval_coverage_complete),
        "required_evals_present": bool(required_evals_present),
        "no_blocking_policy_violations": bool(no_blocking_policy_violations),
        "no_replay_mismatch": bool(no_replay_mismatch),
        "no_schema_failure": bool(no_schema_failure),
        "no_trace_failure": bool(no_trace_failure),
        "no_blocking_unknown_state_signal": bool(no_blocking_unknown_state_signal),
        "supporting_signal_refs": sorted(set(supporting_signal_refs)),
        "trace_id": trace_id,
    }
    record = {
        "allow_decision_proof_id": f"ADP-{_canonical_hash(payload)[:12].upper()}",
        **payload,
        "created_at": created_at,
    }
    _validate_schema(record, "allow_decision_proof")
    return record


__all__ = [
    "AutonomyGuardrailError",
    "build_allow_decision_proof",
    "build_decision_proof_record",
    "build_unknown_state_signal",
    "evaluate_autonomy_guardrails",
]

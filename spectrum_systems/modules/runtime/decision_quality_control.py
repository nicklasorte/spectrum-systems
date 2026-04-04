"""Deterministic decision-quality budgets, calibration, and promotion gate hardening (LT-05/06/09)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from spectrum_systems.contracts import validate_artifact

def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:12].upper()}"


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _severity_for_budget(*, exhausted: bool, wrong_approve_rate: float, wrong_block_rate: float, override_rate: float, review_load_rate: float, thresholds: dict[str, float]) -> str:
    if exhausted:
        return "block"
    if any(metric >= float(thresholds["freeze_candidate"]) for metric in (wrong_approve_rate, wrong_block_rate, override_rate, review_load_rate)):
        return "freeze_candidate"
    if any(metric >= float(thresholds["warning"]) for metric in (wrong_approve_rate, wrong_block_rate, override_rate, review_load_rate)):
        return "warning"
    return "none"


def evaluate_decision_quality_budget(
    *,
    decision_quality_budget_id: str,
    scope: dict[str, str],
    failure_taxonomy_records: list[dict[str, Any]],
    override_governance_records: list[dict[str, Any]],
    eval_results: list[dict[str, Any]],
    promotion_consistency_records: list[dict[str, Any]],
    drift_signals: list[dict[str, Any]],
    budget_thresholds: dict[str, float],
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    """Compute deterministic decision-quality budget status and fail closed on missing mandatory inputs."""
    required_inputs = {
        "failure_taxonomy_records": failure_taxonomy_records,
        "override_governance_records": override_governance_records,
        "eval_results": eval_results,
        "promotion_consistency_records": promotion_consistency_records,
        "drift_signals": drift_signals,
    }
    missing_inputs = sorted(name for name, values in required_inputs.items() if not isinstance(values, list) or not values)
    if missing_inputs:
        raise ValueError(f"missing required decision-quality inputs: {','.join(missing_inputs)}")

    if not {"safe", "warning", "freeze_candidate", "block"}.issubset(set(budget_thresholds.keys())):
        raise ValueError("decision-quality budget thresholds must include safe/warning/freeze_candidate/block")

    total_eval = len(eval_results)
    wrong_approve = 0
    wrong_block = 0
    for row in eval_results:
        if not isinstance(row, dict):
            continue
        outcome = str(row.get("result_status") or row.get("status") or "").strip().lower()
        decision = str(row.get("decision") or row.get("gate_decision") or row.get("system_decision") or "").strip().lower()
        if decision in {"allow", "approve", "continue", "pass"} and outcome in {"fail", "failed", "error", "block"}:
            wrong_approve += 1
        if decision in {"deny", "block", "hold", "stop", "reject"} and outcome in {"pass", "passed", "success", "allow"}:
            wrong_block += 1

    override_rate = _rate(
        sum(1 for row in override_governance_records if isinstance(row, dict) and str(row.get("override_state") or "").lower() not in {"none", "inactive", "expired"}),
        len(override_governance_records),
    )
    review_load_rate = _rate(
        sum(1 for row in failure_taxonomy_records if isinstance(row, dict) and str(row.get("severity") or "").lower() in {"high", "critical"}),
        len(failure_taxonomy_records),
    )
    drift_blockers = sum(1 for row in drift_signals if isinstance(row, dict) and (bool(row.get("drift_detected")) or str(row.get("drift_level") or "").lower() in {"medium", "high", "critical"}))
    promotion_denials = sum(1 for row in promotion_consistency_records if isinstance(row, dict) and str(row.get("promotion_state") or "").lower() in {"hold", "deny"})

    wrong_approve_rate = _rate(wrong_approve, total_eval)
    wrong_block_rate = _rate(wrong_block, total_eval)
    budget_exhausted = (
        wrong_approve_rate >= float(budget_thresholds["block"])
        or wrong_block_rate >= float(budget_thresholds["block"])
        or override_rate >= float(budget_thresholds["block"])
        or review_load_rate >= float(budget_thresholds["block"])
        or drift_blockers > 0
        or promotion_denials > 0
    )
    severity = _severity_for_budget(
        exhausted=budget_exhausted,
        wrong_approve_rate=wrong_approve_rate,
        wrong_block_rate=wrong_block_rate,
        override_rate=override_rate,
        review_load_rate=review_load_rate,
        thresholds={
            "warning": float(budget_thresholds["warning"]),
            "freeze_candidate": float(budget_thresholds["freeze_candidate"]),
        },
    )
    if budget_exhausted:
        severity = "block" if severity != "block" else severity

    reason_codes: list[str] = []
    if wrong_approve_rate >= float(budget_thresholds["warning"]):
        reason_codes.append("wrong_approve_rate_high")
    if wrong_block_rate >= float(budget_thresholds["warning"]):
        reason_codes.append("wrong_block_rate_high")
    if override_rate >= float(budget_thresholds["warning"]):
        reason_codes.append("override_rate_high")
    if review_load_rate >= float(budget_thresholds["warning"]):
        reason_codes.append("review_load_rate_high")
    if drift_blockers > 0:
        reason_codes.append("drift_instability_present")
    if promotion_denials > 0:
        reason_codes.append("promotion_consistency_not_allow")
    if not reason_codes:
        reason_codes.append("within_budget")

    payload = {
        "decision_quality_budget_id": decision_quality_budget_id,
        "scope": {
            "artifact_family": str(scope.get("artifact_family") or "runtime"),
            "route": str(scope.get("route") or "system_cycle"),
            "policy": str(scope.get("policy") or "promotion_hardening"),
            "judgment_class": str(scope.get("judgment_class") or "judgment_required"),
        },
        "wrong_approve_rate": wrong_approve_rate,
        "wrong_block_rate": wrong_block_rate,
        "override_rate": override_rate,
        "review_load_rate": review_load_rate,
        "budget_thresholds": {
            "safe": float(budget_thresholds["safe"]),
            "warning": float(budget_thresholds["warning"]),
            "freeze_candidate": float(budget_thresholds["freeze_candidate"]),
            "block": float(budget_thresholds["block"]),
        },
        "budget_exhausted": bool(budget_exhausted),
        "severity": severity,
        "reason_codes": sorted(set(reason_codes)),
        "created_at": created_at,
        "trace_id": trace_id,
    }
    validate_artifact(payload, "decision_quality_budget_status")
    return payload


def evaluate_calibration(
    *,
    calibration_id: str,
    scope: dict[str, str],
    judgment_records: list[dict[str, Any]],
    eval_results: list[dict[str, Any]],
    post_hoc_correctness_signals: list[dict[str, Any]],
    prior_calibration_assessment: dict[str, Any] | None,
    sample_window_size: int,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    if sample_window_size <= 0:
        raise ValueError("sample_window_size must be positive")
    if not isinstance(judgment_records, list) or not judgment_records:
        raise ValueError("missing required calibration inputs: judgment_records")
    if not isinstance(eval_results, list) or not eval_results:
        raise ValueError("missing required calibration inputs: eval_results")

    confidence_rows = [row for row in judgment_records if isinstance(row, dict)][-sample_window_size:]
    correctness_rows = [row for row in post_hoc_correctness_signals if isinstance(row, dict)][-sample_window_size:]
    if not correctness_rows:
        correctness_rows = [row for row in eval_results if isinstance(row, dict)][-sample_window_size:]

    confidence_values = [float(row.get("confidence", row.get("score", 0.0))) for row in confidence_rows]
    correctness_values = []
    for row in correctness_rows:
        raw = str(row.get("correctness") or row.get("result_status") or row.get("status") or "").lower()
        correctness_values.append(1.0 if raw in {"correct", "pass", "passed", "success", "allow"} else 0.0)

    observed = min(len(confidence_values), len(correctness_values))
    if observed <= 0:
        raise ValueError("calibration requires at least one aligned confidence/correctness datapoint")

    confidence_values = confidence_values[-observed:]
    correctness_values = correctness_values[-observed:]
    calibration_error = round(sum(abs(c - k) for c, k in zip(confidence_values, correctness_values)) / observed, 6)
    overconfidence_rate = _rate(sum(1 for c, k in zip(confidence_values, correctness_values) if c >= 0.7 and k < 1.0), observed)
    underconfidence_rate = _rate(sum(1 for c, k in zip(confidence_values, correctness_values) if c <= 0.4 and k >= 1.0), observed)

    prior_error = float((prior_calibration_assessment or {}).get("calibration_error", calibration_error))
    raw_delta = round(calibration_error - prior_error, 6)
    if raw_delta < 0:
        drift_delta = round(raw_delta * 0.5, 6)
    else:
        drift_delta = round(raw_delta, 6)

    payload = {
        "calibration_id": calibration_id,
        "scope": {
            "artifact_family": str(scope.get("artifact_family") or "runtime"),
            "route": str(scope.get("route") or "judgment"),
            "policy": str(scope.get("policy") or "judgment_promotion"),
            "judgment_class": str(scope.get("judgment_class") or "required"),
        },
        "sample_window_size": observed,
        "confidence_distribution": {
            "high": sum(1 for value in confidence_values if value >= 0.7),
            "medium": sum(1 for value in confidence_values if 0.4 < value < 0.7),
            "low": sum(1 for value in confidence_values if value <= 0.4),
        },
        "correctness_distribution": {
            "correct": sum(1 for value in correctness_values if value >= 1.0),
            "incorrect": sum(1 for value in correctness_values if value < 1.0),
        },
        "calibration_error": calibration_error,
        "overconfidence_rate": overconfidence_rate,
        "underconfidence_rate": underconfidence_rate,
        "drift_delta": drift_delta,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    validate_artifact(payload, "calibration_assessment_record")
    return payload


def evaluate_judgment_promotion_gate(
    *,
    source_batch_id: str,
    required_judgment_refs: list[str],
    decision_quality_budget_status: dict[str, Any] | None,
    calibration_assessment_record: dict[str, Any] | None,
    promotion_consistency_record: dict[str, Any] | None,
    supporting_artifact_refs: list[str],
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    reason_codes: list[str] = []
    decision = "allow"

    if not required_judgment_refs:
        decision = "deny"
        reason_codes.append("required_judgment_refs_missing")
        required_judgment_refs = ["judgment_record:MISSING"]

    if not isinstance(decision_quality_budget_status, dict):
        decision = "deny"
        reason_codes.append("decision_quality_budget_status_missing")
    if not isinstance(calibration_assessment_record, dict):
        decision = "deny"
        reason_codes.append("calibration_assessment_record_missing")
    if not isinstance(promotion_consistency_record, dict):
        decision = "deny"
        reason_codes.append("promotion_consistency_record_missing")

    judgment_eval_pass_rate = 0.0
    if isinstance(calibration_assessment_record, dict):
        correct = int(calibration_assessment_record.get("correctness_distribution", {}).get("correct", 0))
        total = correct + int(calibration_assessment_record.get("correctness_distribution", {}).get("incorrect", 0))
        judgment_eval_pass_rate = _rate(correct, total)

    calibration_status = "good"
    if isinstance(calibration_assessment_record, dict):
        err = float(calibration_assessment_record.get("calibration_error", 1.0))
        delta = float(calibration_assessment_record.get("drift_delta", 0.0))
        if err >= 0.2 or delta > 0.05:
            calibration_status = "poor"
        elif err >= 0.1:
            calibration_status = "degraded"
    else:
        calibration_status = "poor"

    consistency_status = "consistent"
    if isinstance(promotion_consistency_record, dict):
        if int(promotion_consistency_record.get("runs_considered", 0)) < 3:
            consistency_status = "insufficient_evidence"
        elif str(promotion_consistency_record.get("promotion_state") or "hold") != "allow":
            consistency_status = "inconsistent"
    else:
        consistency_status = "inconsistent"

    if isinstance(decision_quality_budget_status, dict):
        if bool(decision_quality_budget_status.get("budget_exhausted")):
            decision = "deny"
            reason_codes.append("decision_quality_budget_exhausted")
        elif str(decision_quality_budget_status.get("severity") or "none") in {"freeze_candidate", "block"}:
            decision = "hold"
            reason_codes.append("decision_quality_budget_escalated")

    if calibration_status == "poor":
        decision = "deny"
        reason_codes.append("calibration_below_threshold")
    elif calibration_status == "degraded" and decision != "deny":
        decision = "hold"
        reason_codes.append("calibration_degraded")

    if consistency_status == "insufficient_evidence" and decision != "deny":
        decision = "hold"
        reason_codes.append("multi_run_evidence_insufficient")
    if consistency_status == "inconsistent":
        decision = "deny"
        reason_codes.append("replay_consistency_not_satisfied")

    if judgment_eval_pass_rate < 0.85:
        decision = "deny"
        reason_codes.append("judgment_eval_coverage_incomplete")

    if not reason_codes:
        reason_codes = ["promotion_gate_satisfied"]

    payload = {
        "promotion_gate_id": _stable_id(
            "JPG",
            {
                "source_batch_id": source_batch_id,
                "required_judgment_refs": sorted(set(required_judgment_refs)),
                "reason_codes": sorted(set(reason_codes)),
                "created_at": created_at,
                "trace_id": trace_id,
            },
        ),
        "source_batch_id": source_batch_id,
        "required_judgment_refs": sorted(set(required_judgment_refs)),
        "judgment_eval_pass_rate": judgment_eval_pass_rate,
        "calibration_status": calibration_status,
        "consistency_status": consistency_status,
        "promotion_decision": decision,
        "reason_codes": sorted(set(reason_codes)),
        "supporting_artifact_refs": sorted(set(supporting_artifact_refs)),
        "created_at": created_at,
        "trace_id": trace_id,
    }
    validate_artifact(payload, "judgment_promotion_gate_record")
    return payload


__all__ = [
    "evaluate_calibration",
    "evaluate_decision_quality_budget",
    "evaluate_judgment_promotion_gate",
]

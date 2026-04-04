"""Deterministic continuous evaluation, budget enforcement, canary rollout, and trust observability artifacts (BATCH-12)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ContinuousGovernanceError(ValueError):
    """Raised when continuous governance artifacts cannot be safely derived."""


_REQUIRED_STAGES = ("offline", "pre_merge", "canary", "production")


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_schema(instance: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ContinuousGovernanceError(f"{schema_name} validation failed: {details}")


def _rate(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 6)


def build_continuous_eval_run_records(
    *,
    artifact_family: str,
    eval_inputs_by_stage: dict[str, dict[str, Any]],
    created_at: str,
    trace_id: str,
    require_all_stages: bool = True,
) -> list[dict[str, Any]]:
    missing = [stage for stage in _REQUIRED_STAGES if stage not in eval_inputs_by_stage]
    if missing and require_all_stages:
        raise ContinuousGovernanceError(f"missing required continuous eval stages: {','.join(missing)}")

    records: list[dict[str, Any]] = []
    for stage in _REQUIRED_STAGES:
        stage_input = dict(eval_inputs_by_stage.get(stage) or {})
        case_ids = sorted({str(item) for item in stage_input.get("eval_case_ids", []) if str(item).strip()})
        if not case_ids:
            case_ids = [f"case:{stage}:default"]
        pass_rate = _rate(float(stage_input.get("pass_rate", 1.0 if stage != "production" else 0.95)))
        fail_rate = _rate(float(stage_input.get("fail_rate", 0.0)))
        indeterminate_rate = _rate(float(stage_input.get("indeterminate_rate", max(0.0, 1.0 - pass_rate - fail_rate))))
        drift_delta = round(float(stage_input.get("drift_delta", 0.0)), 6)
        seed = {
            "artifact_family": artifact_family,
            "eval_stage": stage,
            "eval_case_ids": case_ids,
            "pass_rate": pass_rate,
            "fail_rate": fail_rate,
            "indeterminate_rate": indeterminate_rate,
            "drift_delta": drift_delta,
            "trace_id": trace_id,
        }
        record = {
            "eval_run_id": f"CER-{_canonical_hash(seed)[:12].upper()}",
            "schema_version": "1.0.0",
            "eval_stage": stage,
            "artifact_family": artifact_family,
            "eval_case_ids": case_ids,
            "pass_rate": pass_rate,
            "fail_rate": fail_rate,
            "indeterminate_rate": indeterminate_rate,
            "drift_delta": drift_delta,
            "created_at": created_at,
            "trace_id": trace_id,
        }
        _validate_schema(record, "continuous_eval_run_record")
        records.append(record)
    return records


def build_system_budget_status(
    *,
    threshold_values: dict[str, float],
    current_values: dict[str, float],
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    def _status(curr: float, threshold: float) -> str:
        if curr > threshold:
            return "breached"
        if curr >= threshold * 0.9:
            return "warning"
        return "within_budget"

    thresholds = {
        "cost": round(float(threshold_values.get("cost", 0.0)), 6),
        "latency_ms": round(float(threshold_values.get("latency_ms", 0.0)), 6),
        "error_rate": _rate(float(threshold_values.get("error_rate", 0.0))),
    }
    current = {
        "cost": round(float(current_values.get("cost", 0.0)), 6),
        "latency_ms": round(float(current_values.get("latency_ms", 0.0)), 6),
        "error_rate": _rate(float(current_values.get("error_rate", 0.0))),
    }

    cost_status = _status(current["cost"], thresholds["cost"])
    latency_status = _status(current["latency_ms"], thresholds["latency_ms"])
    error_status = _status(current["error_rate"], thresholds["error_rate"])
    exhausted = "breached" in {cost_status, latency_status, error_status}

    seed = {"thresholds": thresholds, "current": current, "trace_id": trace_id}
    record = {
        "budget_status_id": f"SBS-{_canonical_hash(seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "cost_budget_status": cost_status,
        "latency_budget_status": latency_status,
        "error_budget_status": error_status,
        "budget_exhausted": exhausted,
        "threshold_values": thresholds,
        "current_values": current,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(record, "system_budget_status")
    return record


def build_canary_rollout_record(
    *,
    target_change: str,
    rollout_stage: str,
    sample_size: int,
    eval_run_record: dict[str, Any],
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    _validate_schema(eval_run_record, "continuous_eval_run_record")
    if rollout_stage == "full" and eval_run_record.get("eval_stage") != "canary":
        raise ContinuousGovernanceError("full rollout requires canary eval evidence")

    pass_rate = float(eval_run_record.get("pass_rate", 0.0))
    fail_rate = float(eval_run_record.get("fail_rate", 1.0))
    if pass_rate >= 0.95 and fail_rate <= 0.05:
        promotion_decision = "promote" if rollout_stage == "canary" else "hold"
    elif fail_rate >= 0.2:
        promotion_decision = "rollback"
    else:
        promotion_decision = "block"

    seed = {
        "target_change": target_change,
        "rollout_stage": rollout_stage,
        "sample_size": int(sample_size),
        "eval_run_id": eval_run_record["eval_run_id"],
        "promotion_decision": promotion_decision,
        "trace_id": trace_id,
    }
    record = {
        "rollout_id": f"CNR-{_canonical_hash(seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "target_change": target_change,
        "rollout_stage": rollout_stage,
        "sample_size": int(sample_size),
        "eval_results_ref": f"continuous_eval_run_record:{eval_run_record['eval_run_id']}",
        "promotion_decision": promotion_decision,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(record, "canary_rollout_record")
    return record


def build_observability_reports(
    *,
    eval_run_records: list[dict[str, Any]],
    budget_status: dict[str, Any],
    readiness_state: str,
    replay_status: str,
    override_rate: float,
    created_at: str,
    trace_id: str,
) -> dict[str, dict[str, Any]]:
    for record in eval_run_records:
        _validate_schema(record, "continuous_eval_run_record")
    _validate_schema(budget_status, "system_budget_status")

    eval_pass_rate = round(sum(float(item["pass_rate"]) for item in eval_run_records) / max(1, len(eval_run_records)), 6)
    max_drift = max((abs(float(item["drift_delta"])) for item in eval_run_records), default=0.0)
    drift_status = "drift_detected" if max_drift >= 0.2 else ("warning" if max_drift > 0 else "stable")
    replay_consistency = "consistent" if replay_status in {"passed", "match", "ready", "replayable"} else (
        "unknown" if replay_status == "unknown" else "inconsistent"
    )

    trust_state = "healthy"
    if budget_status["budget_exhausted"] or replay_consistency == "inconsistent":
        trust_state = "critical"
    elif drift_status == "drift_detected" or readiness_state == "unsafe":
        trust_state = "degraded"
    elif drift_status == "warning" or readiness_state == "constrained":
        trust_state = "watch"

    snapshot_seed = {
        "eval_pass_rate": eval_pass_rate,
        "drift_status": drift_status,
        "replay_consistency": replay_consistency,
        "override_rate": _rate(override_rate),
        "readiness_state": readiness_state,
        "trust_state": trust_state,
        "trace_id": trace_id,
    }
    trust_posture_snapshot = {
        "snapshot_id": f"TPS-{_canonical_hash(snapshot_seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "overall_trust_state": trust_state,
        "eval_pass_rate": eval_pass_rate,
        "drift_status": drift_status,
        "replay_consistency": replay_consistency,
        "override_rate": _rate(override_rate),
        "readiness_state": readiness_state,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(trust_posture_snapshot, "trust_posture_snapshot")

    family = eval_run_records[0]["artifact_family"] if eval_run_records else "system_cycle"
    reason_codes = []
    if budget_status["budget_exhausted"]:
        reason_codes.append("budget_exhausted")
    if drift_status != "stable":
        reason_codes.append(f"drift_status:{drift_status}")
    if replay_consistency != "consistent":
        reason_codes.append(f"replay_consistency:{replay_consistency}")
    if not reason_codes:
        reason_codes = ["healthy"]

    family_seed = {"family": family, "reason_codes": sorted(reason_codes), "trace_id": trace_id}
    family_report = {
        "report_id": f"AFH-{_canonical_hash(family_seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "artifact_family": family,
        "health_state": trust_state,
        "reason_codes": sorted(reason_codes),
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(family_report, "artifact_family_health_report")

    seen_stages = {str(item.get("eval_stage")) for item in eval_run_records}
    missing_stages = sorted(set(_REQUIRED_STAGES) - seen_stages)
    gap_seed = {"family": family, "missing_stages": missing_stages or ["none"], "trace_id": trace_id}
    evidence_gap = {
        "report_id": f"EGH-{_canonical_hash(gap_seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "hotspots": [{"artifact_family": family, "missing_stages": missing_stages or ["offline"]}],
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(evidence_gap, "evidence_gap_hotspot_report")

    override_seed = {"family": family, "override_rate": _rate(override_rate), "trace_id": trace_id}
    override_report = {
        "report_id": f"OVH-{_canonical_hash(override_seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "hotspots": [{"artifact_family": family, "override_rate": _rate(override_rate)}],
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(override_report, "override_hotspot_report")

    return {
        "trust_posture_snapshot": trust_posture_snapshot,
        "artifact_family_health_report": family_report,
        "evidence_gap_hotspot_report": evidence_gap,
        "override_hotspot_report": override_report,
    }


__all__ = [
    "ContinuousGovernanceError",
    "build_canary_rollout_record",
    "build_continuous_eval_run_records",
    "build_observability_reports",
    "build_system_budget_status",
]

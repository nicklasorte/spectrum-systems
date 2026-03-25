"""Deterministic runtime/replay observability metrics builder."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

SCHEMA_VERSION = "1.0.0"
_GENERATED_BY_VERSION = "observability_metrics.py@1.0.0"
_ALLOWED_SOURCE_TYPES = frozenset({
    "replay_result",
    "grounding_control_decision",
    "drift_detection_result",
    "baseline_gate_decision",
    "regression_run_result",
})


def _detect_artifact_type(artifact: Dict[str, Any]) -> str:
    artifact_type = artifact.get("artifact_type")
    if isinstance(artifact_type, str) and artifact_type in _ALLOWED_SOURCE_TYPES:
        return artifact_type

    # Legacy/governed artifacts without explicit artifact_type field
    if "decision_id" in artifact and "grounding_eval_id" in artifact and "failure_summary" in artifact:
        return "grounding_control_decision"
    if "decision_id" in artifact and "drift_result_id" in artifact and "enforcement_action" in artifact:
        return "baseline_gate_decision"
    if "run_id" in artifact and "suite_id" in artifact and "failed_traces" in artifact:
        return "regression_run_result"

    raise ObservabilityMetricsError(f"unsupported source artifact_type: {artifact_type!r}")
_SLO_METRICS = frozenset({
    "replay_success_rate",
    "grounding_block_rate",
    "unsupported_claim_rate",
    "invalid_evidence_ref_rate",
    "drift_exceed_threshold_rate",
    "baseline_gate_block_rate",
    "regression_failure_rate",
})


class ObservabilityMetricsError(ValueError):
    """Raised for deterministic fail-closed observability metric failures."""


def _validate_or_raise(instance: Dict[str, Any], schema_name: str, *, context: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ObservabilityMetricsError(f"{context} failed validation: {details}")


def _stable_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObservabilityMetricsError(f"{field_name} must be a non-empty string")
    return value


def _require_rate(value: Any, field_name: str) -> float:
    rate = float(value)
    if rate < 0.0 or rate > 1.0:
        raise ObservabilityMetricsError(f"{field_name} must be between 0.0 and 1.0")
    return rate


def load_slo_definition(slo_definition: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(slo_definition, dict):
        raise ObservabilityMetricsError("slo_definition must be an object")
    normalized = deepcopy(slo_definition)
    _validate_or_raise(normalized, "service_level_objective", context="service_level_objective")
    for objective in normalized.get("objectives") or []:
        metric_name = objective.get("metric_name")
        if metric_name not in _SLO_METRICS:
            raise ObservabilityMetricsError(f"unsupported SLO metric_name: {metric_name!r}")
    return normalized


def _collect_timestamp(artifacts: Sequence[Dict[str, Any]]) -> str:
    timestamps: List[str] = []
    for artifact in artifacts:
        timestamp = artifact.get("timestamp") or artifact.get("created_at") or artifact.get("replayed_at")
        timestamps.append(_require_non_empty_str(timestamp, "source artifact timestamp"))
    return sorted(timestamps)[-1]


def _collect_trace_id(artifacts: Sequence[Dict[str, Any]], explicit_trace_id: Optional[str]) -> str:
    if explicit_trace_id is not None:
        return _require_non_empty_str(explicit_trace_id, "trace_id")

    trace_ids = set()
    for artifact in artifacts:
        if isinstance(artifact.get("trace_refs"), dict) and artifact["trace_refs"].get("trace_id"):
            trace_ids.add(str(artifact["trace_refs"]["trace_id"]))
        elif artifact.get("trace_id"):
            trace_ids.add(str(artifact.get("trace_id")))
        elif isinstance(artifact.get("trace_linkage"), dict) and artifact["trace_linkage"].get("trace_id"):
            trace_ids.add(str(artifact["trace_linkage"]["trace_id"]))

    if not trace_ids:
        raise ObservabilityMetricsError("no trace_id available across source artifacts")
    if len(trace_ids) != 1:
        raise ObservabilityMetricsError("source artifacts must share exactly one trace_id")
    return next(iter(trace_ids))


def _collect_run_ids(artifacts: Sequence[Dict[str, Any]]) -> List[str]:
    run_ids = set()
    for artifact in artifacts:
        artifact_type = _detect_artifact_type(artifact)
        if artifact_type == "replay_result":
            run_ids.add(_require_non_empty_str(artifact.get("replay_run_id"), "replay_result.replay_run_id"))
        elif artifact_type == "grounding_control_decision":
            run_ids.add(_require_non_empty_str(artifact.get("run_id"), "grounding_control_decision.run_id"))
        elif artifact_type == "drift_detection_result":
            run_ids.add(_require_non_empty_str(artifact.get("run_id"), "drift_detection_result.run_id"))
        elif artifact_type == "baseline_gate_decision":
            run_ids.add(_require_non_empty_str(artifact.get("run_id"), "baseline_gate_decision.run_id"))
        elif artifact_type == "regression_run_result":
            run_ids.add(_require_non_empty_str(artifact.get("run_id"), "regression_run_result.run_id"))
    if not run_ids:
        raise ObservabilityMetricsError("at least one run_id is required")
    return sorted(run_ids)


def _collect_artifact_ids(artifacts: Sequence[Dict[str, Any]]) -> List[str]:
    ids = set()
    for artifact in artifacts:
        artifact_type = _detect_artifact_type(artifact)
        if artifact_type == "replay_result":
            ids.add(_require_non_empty_str(artifact.get("replay_id"), "replay_result.replay_id"))
        elif artifact_type == "grounding_control_decision":
            ids.add(_require_non_empty_str(artifact.get("decision_id"), "grounding_control_decision.decision_id"))
        elif artifact_type == "drift_detection_result":
            ids.add(_require_non_empty_str(artifact.get("artifact_id"), "drift_detection_result.artifact_id"))
        elif artifact_type == "baseline_gate_decision":
            ids.add(_require_non_empty_str(artifact.get("decision_id"), "baseline_gate_decision.decision_id"))
        elif artifact_type == "regression_run_result":
            ids.add(_require_non_empty_str(artifact.get("run_id"), "regression_run_result.run_id"))
    if not ids:
        raise ObservabilityMetricsError("at least one source_artifact_id is required")
    return sorted(ids)


def _evaluate_slo(metrics: Dict[str, Any], slo_definition: Optional[Dict[str, Any]]) -> tuple[Optional[str], Optional[str], Dict[str, Any]]:
    if slo_definition is None:
        return None, None, {"breached_metrics": [], "highest_severity": "none", "reasons": []}

    slo = load_slo_definition(slo_definition)
    breached: List[str] = []
    reasons: List[str] = []
    highest = "none"
    highest_rank = 0
    ranks = {"none": 0, "warn": 1, "block": 2}

    for objective in slo.get("objectives") or []:
        metric_name = objective["metric_name"]
        if metric_name not in metrics:
            raise ObservabilityMetricsError(
                f"SLO objective metric {metric_name!r} is not computable from provided source artifacts"
            )

        measured = float(metrics[metric_name])
        target = float(objective["target_value"])
        operator = objective["target_operator"]
        if operator == "gte":
            passed = measured >= target
        elif operator == "lte":
            passed = measured <= target
        elif operator == "eq":
            passed = measured == target
        else:
            raise ObservabilityMetricsError(f"unsupported target_operator: {operator!r}")

        if not passed:
            breached.append(metric_name)
            severity = objective["severity_on_breach"]
            if ranks[severity] > highest_rank:
                highest = severity
                highest_rank = ranks[severity]
            reasons.append(
                f"{metric_name} breached: measured={measured:.6f} operator={operator} target={target:.6f}"
            )

    return slo["slo_id"], slo["policy_id"], {
        "breached_metrics": sorted(set(breached)),
        "highest_severity": highest,
        "reasons": reasons,
    }


def build_observability_metrics(
    source_artifacts: Sequence[Dict[str, Any]],
    slo_definition: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
    *,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not isinstance(source_artifacts, list) or not source_artifacts:
        raise ObservabilityMetricsError("source_artifacts must be a non-empty list")

    artifacts = [deepcopy(artifact) for artifact in source_artifacts]

    counts: Dict[str, int] = {
        "replay_total": 0,
        "replay_success": 0,
        "grounding_total": 0,
        "grounding_block": 0,
        "grounding_claims_total": 0,
        "grounding_unsupported_claims": 0,
        "grounding_invalid_refs": 0,
        "drift_total": 0,
        "drift_exceeds": 0,
        "baseline_total": 0,
        "baseline_block": 0,
        "regression_total": 0,
        "regression_failed": 0,
    }

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ObservabilityMetricsError("all source artifacts must be objects")
        artifact_type = _detect_artifact_type(artifact)

        _validate_or_raise(artifact, artifact_type, context=f"{artifact_type} source artifact")

        if artifact_type == "replay_result":
            counts["replay_total"] += 1
            if artifact.get("consistency_status") == "match":
                counts["replay_success"] += 1
        elif artifact_type == "grounding_control_decision":
            counts["grounding_total"] += 1
            if artifact.get("status") == "block":
                counts["grounding_block"] += 1
            failure_summary = artifact.get("failure_summary")
            if not isinstance(failure_summary, dict):
                raise ObservabilityMetricsError("grounding_control_decision.failure_summary must be an object")
            total_claims = int(failure_summary.get("total_claims"))
            unsupported_claims = int(failure_summary.get("unsupported_claims"))
            invalid_refs = int(failure_summary.get("invalid_evidence_refs"))
            if total_claims < 0 or unsupported_claims < 0 or invalid_refs < 0:
                raise ObservabilityMetricsError("grounding_control_decision failure_summary counts must be >= 0")
            if unsupported_claims > total_claims or invalid_refs > total_claims:
                raise ObservabilityMetricsError("grounding_control_decision failure_summary counts are inconsistent")
            counts["grounding_claims_total"] += total_claims
            counts["grounding_unsupported_claims"] += unsupported_claims
            counts["grounding_invalid_refs"] += invalid_refs
        elif artifact_type == "drift_detection_result":
            counts["drift_total"] += 1
            if artifact.get("drift_status") == "exceeds_threshold":
                counts["drift_exceeds"] += 1
        elif artifact_type == "baseline_gate_decision":
            counts["baseline_total"] += 1
            if artifact.get("status") == "block":
                counts["baseline_block"] += 1
        elif artifact_type == "regression_run_result":
            counts["regression_total"] += int(artifact.get("total_traces"))
            counts["regression_failed"] += int(artifact.get("failed_traces"))

    if counts["replay_total"] == 0:
        raise ObservabilityMetricsError("at least one replay_result artifact is required")

    metrics: Dict[str, Any] = {
        "total_runs": counts["replay_total"],
        "replay_success_rate": round(counts["replay_success"] / counts["replay_total"], 6),
    }

    if counts["grounding_total"] > 0:
        metrics["grounding_block_rate"] = round(counts["grounding_block"] / counts["grounding_total"], 6)
        if counts["grounding_claims_total"] == 0:
            raise ObservabilityMetricsError("grounding claim metrics require total_claims > 0")
        metrics["unsupported_claim_rate"] = round(
            counts["grounding_unsupported_claims"] / counts["grounding_claims_total"], 6
        )
        metrics["invalid_evidence_ref_rate"] = round(
            counts["grounding_invalid_refs"] / counts["grounding_claims_total"], 6
        )

    if counts["drift_total"] > 0:
        metrics["drift_exceed_threshold_rate"] = round(counts["drift_exceeds"] / counts["drift_total"], 6)

    if counts["baseline_total"] > 0:
        metrics["baseline_gate_block_rate"] = round(counts["baseline_block"] / counts["baseline_total"], 6)

    if counts["regression_total"] > 0:
        metrics["regression_failure_rate"] = round(counts["regression_failed"] / counts["regression_total"], 6)

    slo_id, policy_id, breach_summary = _evaluate_slo(metrics, slo_definition)
    if policy is not None and policy_id is None:
        policy_id = _require_non_empty_str(policy.get("policy_id"), "policy.policy_id")

    resolved_trace_id = _collect_trace_id(artifacts, trace_id)
    timestamp = _collect_timestamp(artifacts)
    run_ids = _collect_run_ids(artifacts)
    source_ids = _collect_artifact_ids(artifacts)

    result = {
        "artifact_id": "",
        "artifact_type": "observability_metrics",
        "schema_version": SCHEMA_VERSION,
        "timestamp": timestamp,
        "trace_refs": {"trace_id": resolved_trace_id},
        "measurement_scope": "single_replay_run" if len(run_ids) == 1 else "batch_runtime_replay",
        "run_ids": run_ids,
        "source_artifact_ids": source_ids,
        "metric_window": "single_run" if len(run_ids) == 1 else "rolling_batch",
        "metrics": metrics,
        "slo_id": slo_id,
        "policy_id": policy_id,
        "breach_summary": breach_summary,
        "generated_by_version": _GENERATED_BY_VERSION,
    }

    preimage = dict(result)
    preimage.pop("artifact_id", None)
    result["artifact_id"] = _stable_id(preimage)
    _validate_or_raise(result, "observability_metrics", context="observability_metrics")
    return result

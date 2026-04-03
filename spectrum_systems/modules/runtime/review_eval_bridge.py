"""Deterministic bridge from ``review_control_signal`` to governed eval artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any, Dict, Iterable, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class ReviewEvalBridgeError(ValueError):
    """Raised when review-derived eval artifact generation fails fail-closed."""


def _validate(artifact: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(artifact)
    except Exception as exc:
        raise ReviewEvalBridgeError(f"{schema_name} validation failed: {exc}") from exc


def _canonical_payload(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _review_trace_id(review_signal: Dict[str, Any]) -> str:
    seed = f"{review_signal['signal_id']}::{review_signal['review_id']}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _review_eval_case_id(review_signal: Dict[str, Any]) -> str:
    return deterministic_id(
        prefix="ec",
        namespace="review_signal_eval_case",
        payload={
            "signal_id": review_signal["signal_id"],
            "review_id": review_signal["review_id"],
            "review_type": review_signal["review_type"],
        },
    )


def canonicalize_review_signal(review_signal: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and validate review signal input deterministically."""
    if not isinstance(review_signal, dict):
        raise ReviewEvalBridgeError("review_control_signal must be an object")
    _validate(review_signal, "review_control_signal")

    critical_findings = sorted({str(item).strip() for item in review_signal.get("critical_findings") or [] if str(item).strip()})
    normalized = {
        "artifact_type": "review_control_signal",
        "schema_version": "1.1.0",
        "signal_id": str(review_signal.get("signal_id") or ""),
        "review_id": str(review_signal.get("review_id") or ""),
        "review_type": str(review_signal.get("review_type") or ""),
        "gate_assessment": str(review_signal.get("gate_assessment") or ""),
        "scale_recommendation": str(review_signal.get("scale_recommendation") or ""),
        "critical_findings": critical_findings,
        "confidence": float(review_signal.get("confidence")),
        "trace_linkage": {
            "review_markdown_path": str(review_signal["trace_linkage"]["review_markdown_path"]),
            "source_digest_sha256": str(review_signal["trace_linkage"]["source_digest_sha256"]),
            "review_artifact_path": str(review_signal["trace_linkage"]["review_artifact_path"]),
        },
    }
    _validate(normalized, "review_control_signal")
    return normalized


def build_eval_result_from_review_signal(review_signal: Dict[str, Any]) -> Dict[str, Any]:
    """Emit deterministic review-derived eval_result artifact."""
    normalized = canonicalize_review_signal(review_signal)
    gate = normalized["gate_assessment"]
    finding_count = len(normalized["critical_findings"])
    if gate == "PASS":
        status = "pass"
        score = 1.0
    elif gate == "FAIL":
        status = "fail"
        score = 0.0
    else:
        status = "indeterminate"
        score = 0.5

    failure_modes: List[str] = []
    if gate == "FAIL":
        failure_modes.append("review_gate_failed")
    if gate == "CONDITIONAL":
        failure_modes.append("review_gate_conditional")
    if normalized["scale_recommendation"] == "NO":
        failure_modes.append("review_scale_not_recommended")
    if finding_count > 0:
        failure_modes.append("review_critical_findings_present")

    identity_payload = {
        "signal_id": normalized["signal_id"],
        "review_id": normalized["review_id"],
        "status": status,
        "failure_modes": failure_modes,
        "findings": normalized["critical_findings"],
    }
    eval_result = {
        "artifact_type": "eval_result",
        "schema_version": "1.0.0",
        "eval_case_id": _review_eval_case_id(normalized),
        "run_id": deterministic_id(prefix="run", namespace="review_eval_run", payload=identity_payload),
        "trace_id": _review_trace_id(normalized),
        "result_status": status,
        "score": score,
        "failure_modes": sorted(dict.fromkeys(failure_modes)),
        "provenance_refs": [
            f"review_control_signal:{normalized['signal_id']}",
            f"review:{normalized['review_id']}",
            f"review_type:{normalized['review_type']}",
            f"review_source_digest:{normalized['trace_linkage']['source_digest_sha256']}",
            f"review_signal_digest:{hashlib.sha256(_canonical_payload(normalized).encode('utf-8')).hexdigest()}",
            f"review_finding_count:{finding_count}",
        ],
    }
    _validate(eval_result, "eval_result")
    return eval_result


def _parse_ref(provenance_refs: list[str], prefix: str) -> str:
    for ref in provenance_refs:
        if ref.startswith(prefix):
            return ref.split(":", 1)[1]
    return ""


def summarize_review_eval_results(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate review-derived eval results for observability/control traceability."""
    materialized = [dict(result) for result in results]
    if not materialized:
        raise ReviewEvalBridgeError("review eval result list must not be empty")
    for item in materialized:
        _validate(item, "eval_result")

    failed = sum(1 for item in materialized if item["result_status"] == "fail")
    indeterminate = sum(1 for item in materialized if item["result_status"] == "indeterminate")
    if failed:
        status = "failing"
    elif indeterminate:
        status = "degraded"
    else:
        status = "healthy"

    trace_id = str(materialized[0]["trace_id"])
    if any(str(item["trace_id"]) != trace_id for item in materialized):
        raise ReviewEvalBridgeError("review eval results must share trace_id for deterministic summary")

    summary = {
        "artifact_type": "review_eval_summary",
        "schema_version": "1.0.0",
        "summary_id": deterministic_id(
            prefix="res",
            namespace="review_eval_summary",
            payload=[
                {
                    "eval_case_id": item["eval_case_id"],
                    "run_id": item["run_id"],
                    "status": item["result_status"],
                    "score": item["score"],
                }
                for item in sorted(materialized, key=lambda x: (x["eval_case_id"], x["run_id"]))
            ],
        ),
        "trace_id": trace_id,
        "failed_eval_count": failed,
        "indeterminate_eval_count": indeterminate,
        "total_eval_count": len(materialized),
        "system_status": status,
        "review_eval_refs": [f"eval_result:{item['run_id']}" for item in materialized],
    }
    return summary


def build_review_failure_summary(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    materialized = [dict(item) for item in results]
    if not materialized:
        raise ReviewEvalBridgeError("results must not be empty")
    for item in materialized:
        _validate(item, "eval_result")
    trace_id = str(materialized[0]["trace_id"])
    if any(str(item["trace_id"]) != trace_id for item in materialized):
        raise ReviewEvalBridgeError("review eval results must share trace_id")

    module_counts: dict[str, int] = {}
    critical_count = 0
    failed = 0
    for item in materialized:
        if item["result_status"] == "fail":
            failed += 1
        count_text = _parse_ref(item.get("provenance_refs") or [], "review_finding_count:")
        if count_text.isdigit():
            critical_count += int(count_text)
        module = _parse_ref(item.get("provenance_refs") or [], "review_type:") or "unknown"
        if item["result_status"] == "fail":
            module_counts[module] = module_counts.get(module, 0) + 1

    artifact = {
        "artifact_type": "review_failure_summary",
        "schema_version": "1.0.0",
        "summary_id": deterministic_id(prefix="rfs", namespace="review_failure_summary", payload=materialized),
        "trace_id": trace_id,
        "total_reviews": len(materialized),
        "failed_reviews": failed,
        "fail_rate": failed / len(materialized),
        "critical_finding_count": critical_count,
        "module_fail_counts": [
            {"module": module, "failed_reviews": module_counts[module]} for module in sorted(module_counts)
        ],
    }
    _validate(artifact, "review_failure_summary")
    return artifact


def _normalize_finding_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def build_review_hotspot_report(review_signals: Iterable[Dict[str, Any]], *, trace_id: str) -> Dict[str, Any]:
    counts: dict[str, int] = {}
    for signal in review_signals:
        normalized = canonicalize_review_signal(signal)
        for finding in normalized["critical_findings"]:
            key = _normalize_finding_key(finding)
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
    hotspots = [
        {
            "normalized_finding_key": key,
            "occurrence_count": counts[key],
            "highest_severity": "critical" if counts[key] >= 3 else "high" if counts[key] == 2 else "medium",
        }
        for key in sorted(counts)
    ]
    artifact = {
        "artifact_type": "review_hotspot_report",
        "schema_version": "1.0.0",
        "report_id": deterministic_id(prefix="rhr", namespace="review_hotspot_report", payload=hotspots),
        "trace_id": trace_id,
        "hotspots": hotspots,
    }
    _validate(artifact, "review_hotspot_report")
    return artifact


__all__ = [
    "ReviewEvalBridgeError",
    "build_eval_result_from_review_signal",
    "build_review_failure_summary",
    "build_review_hotspot_report",
    "canonicalize_review_signal",
    "summarize_review_eval_results",
]

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract


_ALLOWED_FAILURE_SOURCES = {"redteam_finding", "blocked_promotion", "override_event"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conversion_inputs(source_type: str, source_record: Dict[str, Any]) -> tuple[str, str, str, str]:
    if source_type == "redteam_finding":
        finding_id = str(source_record.get("finding_id", ""))
        if not finding_id:
            raise BNEBlockError("red-team finding conversion requires finding_id")
        return finding_id, str(source_record.get("failure_class", "redteam_failure")), str(source_record.get("expected_behavior", "block unsafe output")), str(source_record.get("severity", "HIGH"))

    if source_type == "blocked_promotion":
        case_id = str(source_record.get("case_id", ""))
        if not case_id:
            raise BNEBlockError("blocked promotion conversion requires case_id")
        return case_id, str(source_record.get("failure_class", "promotion_block")), str(source_record.get("expected_behavior", "do not promote without required evals")), "HIGH"

    if source_type == "override_event":
        override_id = str(source_record.get("override_id", ""))
        if not override_id:
            raise BNEBlockError("override conversion requires override_id")
        return override_id, str(source_record.get("failure_class", "override_risk")), str(source_record.get("expected_behavior", "override must preserve fail-closed behavior")), str(source_record.get("severity", "MEDIUM"))

    raise BNEBlockError(f"unsupported conversion source_type: {source_type}")


def convert_failure_to_eval_case(
    *,
    trace_id: str,
    source_type: str | None = None,
    source_record: Dict[str, Any] | None = None,
    source_finding_id: str | None = None,
    failure_class: str | None = None,
    expected_behavior: str | None = None,
    blocking_severity: str | None = None,
) -> Dict[str, Any]:
    if source_type is None and source_finding_id:
        source_type = "redteam_finding"
        source_record = {
            "finding_id": source_finding_id,
            "failure_class": failure_class or "redteam_failure",
            "expected_behavior": expected_behavior or "block unsafe output",
            "severity": blocking_severity or "HIGH",
        }

    if source_type not in _ALLOWED_FAILURE_SOURCES:
        raise BNEBlockError(f"unsupported source_type: {source_type}")
    source_record = source_record or {}

    source_id, failure_class, expected_behavior, blocking_severity = _conversion_inputs(source_type, source_record)
    eval_case_id = f"fde-{source_id}"

    case = ensure_contract(
        {
            "artifact_type": "failure_derived_eval_case",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "created_at": _utc_now(),
            "provenance": {
                "source_system": "RTX" if source_type == "redteam_finding" else "WPG",
                "inputs": [source_id],
                "simulated": False,
            },
            "record_id": eval_case_id,
            "status": "converted",
            "reason_codes": [failure_class],
            "payload": {
                "source_type": source_type,
                "source_id": source_id,
                "failure_class": failure_class,
                "expected_behavior": expected_behavior,
                "blocking_severity": blocking_severity,
            },
        },
        "failure_derived_eval_case",
    )

    regression_case = ensure_contract(
        {
            "artifact_type": "regression_eval_case",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "eval_case_id": f"reg-{source_id}",
            "failure_class": failure_class,
            "source_eval_case_id": eval_case_id,
            "expected_behavior": expected_behavior,
            "binding_scope": "wpg_pipeline",
            "active": True,
        },
        "regression_eval_case",
    )

    rec = ensure_contract(
        {
            "artifact_type": "failure_to_eval_conversion_record",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "source_type": source_type,
                "source_finding_id": source_id,
                "eval_case_id": eval_case_id,
                "regression_eval_case_id": regression_case["eval_case_id"],
                "status": "converted",
                "warnings": [],
            },
        },
        "failure_to_eval_conversion_record",
    )

    return {"case": case, "record": rec, "regression_eval_case": regression_case}


def convert_failures_to_eval_cases(*, trace_id: str, failures: List[Dict[str, Any]]) -> Dict[str, Any]:
    conversions: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for failure in failures:
        source_type = str(failure.get("source_type", ""))
        source_record = failure.get("source_record") or {}
        if not source_type or not source_record:
            warnings.append("missing_conversion_for_failure")
            continue
        conversions.append(convert_failure_to_eval_case(trace_id=trace_id, source_type=source_type, source_record=source_record))

    status = "converted" if conversions else "warn"
    return {
        "artifact_type": "failure_to_eval_conversion_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": {
            "status": status,
            "conversion_count": len(conversions),
            "warnings": warnings,
            "records": [entry["record"]["outputs"] for entry in conversions],
        },
        "conversions": conversions,
    }

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract


def convert_failure_to_eval_case(*, trace_id: str, source_finding_id: str, failure_class: str, expected_behavior: str, blocking_severity: str) -> Dict[str, Any]:
    case = ensure_contract({
        "artifact_type": "failure_derived_eval_case",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "source_system": "RTX",
            "inputs": [source_finding_id],
            "simulated": False,
        },
        "record_id": f"fde-{source_finding_id}",
        "status": "converted",
        "reason_codes": [failure_class],
        "payload": {
            "source_finding_id": source_finding_id,
            "failure_class": failure_class,
            "expected_behavior": expected_behavior,
            "blocking_severity": blocking_severity,
        }
    }, "failure_derived_eval_case")
    rec = ensure_contract({
        "artifact_type": "failure_to_eval_conversion_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": {
            "source_finding_id": source_finding_id,
            "eval_case_id": f"fde-{source_finding_id}",
            "status": "converted",
        },
    }, "failure_to_eval_conversion_record")
    if not rec["outputs"].get("eval_case_id"):
        raise BNEBlockError("invalid conversion record")
    return {"case": case, "record": rec}

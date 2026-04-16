from __future__ import annotations
from typing import Dict, Iterable, List
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract


def build_artifact_intelligence_index(*, trace_id: str, artifacts: Iterable[Dict[str, any]]) -> Dict[str, any]:
    rows: List[Dict[str, any]] = []
    invalid = 0
    for a in artifacts:
        if not isinstance(a, dict) or "artifact_type" not in a:
            invalid += 1
            continue
        rows.append({
            "artifact_type": a.get("artifact_type"),
            "trace_id": a.get("trace_id", trace_id),
            "phase_id": a.get("phase_id", "unknown"),
            "control_decision": a.get("outputs", {}).get("decision", "UNKNOWN"),
            "reason_codes": a.get("outputs", {}).get("reason_codes", []),
            "policy_version": a.get("schema_version", "1.0.0"),
            "time_window": "current",
        })
    if invalid:
        raise BNEBlockError(f"invalid indexed artifacts: {invalid}")
    return ensure_contract({
        "artifact_type": "artifact_intelligence_index_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": {"rows": rows},
    }, "artifact_intelligence_index_record")

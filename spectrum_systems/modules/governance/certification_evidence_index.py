"""Certification evidence index — reference-only packaging seam."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from spectrum_systems.modules.governance.trust_compression import (
    build_certification_delta,
    enforce_proof_size_budget,
)
from spectrum_systems.modules.observability.reason_code_canonicalizer import canonicalize_reason_code

REQUIRED_REFERENCE_FIELDS = (
    "eval_summary_ref",
    "lineage_summary_ref",
    "replay_summary_ref",
    "control_decision_ref",
    "authority_shape_preflight_ref",
    "registry_validation_ref",
    "artifact_tier_validation_ref",
)
OPTIONAL_REFERENCE_FIELDS = ("enforcement_action_ref", "failure_trace_ref")


class CertificationEvidenceIndexError(ValueError):
    pass


def _ref_id(obj: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not isinstance(obj, Mapping):
        return None
    for key in ("artifact_id", "decision_id", "validation_id", "enforcement_id", "index_id", "trace_id", "id"):
        v = obj.get(key)
        if isinstance(v, str) and v.strip():
            return v
    return None


def _status_of(obj: Optional[Mapping[str, Any]], *keys: str) -> str:
    if not isinstance(obj, Mapping):
        return ""
    for key in keys:
        v = obj.get(key)
        if isinstance(v, str) and v.strip():
            return v.lower()
    return ""


def build_certification_evidence_index(
    *,
    index_id: str,
    trace_id: str,
    eval_summary: Optional[Mapping[str, Any]],
    lineage_summary: Optional[Mapping[str, Any]],
    replay_summary: Optional[Mapping[str, Any]],
    control_decision: Optional[Mapping[str, Any]],
    enforcement_action: Optional[Mapping[str, Any]] = None,
    authority_shape_preflight: Optional[Mapping[str, Any]] = None,
    registry_validation: Optional[Mapping[str, Any]] = None,
    artifact_tier_validation: Optional[Mapping[str, Any]] = None,
    failure_trace: Optional[Mapping[str, Any]] = None,
    state_changing: bool = True,
    freshness_status: str = "current",
    previous_evidence_index: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(index_id, str) or not index_id.strip():
        raise CertificationEvidenceIndexError("index_id must be a non-empty string")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise CertificationEvidenceIndexError("trace_id must be a non-empty string")

    refs: Dict[str, Optional[str]] = {
        "eval_summary_ref": _ref_id(eval_summary),
        "lineage_summary_ref": _ref_id(lineage_summary),
        "replay_summary_ref": _ref_id(replay_summary),
        "control_decision_ref": _ref_id(control_decision),
        "enforcement_action_ref": _ref_id(enforcement_action),
        "authority_shape_preflight_ref": _ref_id(authority_shape_preflight),
        "registry_validation_ref": _ref_id(registry_validation),
        "artifact_tier_validation_ref": _ref_id(artifact_tier_validation),
        "failure_trace_ref": _ref_id(failure_trace),
    }

    blocking_detail_codes: List[str] = []
    missing: List[str] = []

    if eval_summary is None:
        missing.append("eval_summary_ref")
        blocking_detail_codes.append("CERT_MISSING_EVAL_PASS")
    else:
        if _status_of(eval_summary, "status", "coverage_completeness_status") not in {"healthy", "complete", "pass", "ok"}:
            blocking_detail_codes.append("CERT_MISSING_EVAL_PASS")

    if lineage_summary is None:
        missing.append("lineage_summary_ref")
        blocking_detail_codes.append("CERT_MISSING_LINEAGE")
    else:
        if _status_of(lineage_summary, "status") not in {"healthy", "ok"}:
            blocking_detail_codes.append("CERT_MISSING_LINEAGE")

    if replay_summary is None:
        missing.append("replay_summary_ref")
        blocking_detail_codes.append("CERT_MISSING_REPLAY_READINESS")
    else:
        if _status_of(replay_summary, "status") not in {"healthy", "ok", "match"}:
            blocking_detail_codes.append("CERT_MISSING_REPLAY_READINESS")

    if control_decision is None:
        missing.append("control_decision_ref")
        blocking_detail_codes.append("CERT_MISSING_CONTROL_DECISION")
    else:
        if _status_of(control_decision, "decision") != "allow":
            blocking_detail_codes.append("CERT_MISSING_CONTROL_DECISION")

    if state_changing and enforcement_action is None:
        missing.append("enforcement_action_ref")
        blocking_detail_codes.append("CERT_MISSING_ENFORCEMENT_RECORD")

    if authority_shape_preflight is None:
        missing.append("authority_shape_preflight_ref")
        blocking_detail_codes.append("CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT")
    elif _status_of(authority_shape_preflight, "status", "preflight_status") != "pass":
        blocking_detail_codes.append("CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT")

    if registry_validation is None:
        missing.append("registry_validation_ref")
        blocking_detail_codes.append("CERT_REGISTRY_VIOLATION_PRESENT")
    else:
        rv_status = _status_of(registry_validation, "status")
        rv_violations = registry_validation.get("violations") if isinstance(registry_validation, Mapping) else None
        if rv_status not in {"pass", "ok", "healthy"} or (isinstance(rv_violations, list) and rv_violations):
            blocking_detail_codes.append("CERT_REGISTRY_VIOLATION_PRESENT")

    if artifact_tier_validation is None:
        missing.append("artifact_tier_validation_ref")
        blocking_detail_codes.append("CERT_EVIDENCE_INDEX_INCOMPLETE")
    elif _status_of(artifact_tier_validation, "decision") != "allow":
        blocking_detail_codes.append("CERT_EVIDENCE_INDEX_INCOMPLETE")

    if freshness_status in {"stale", "unknown"}:
        blocking_detail_codes.append("CERT_EVIDENCE_INDEX_INCOMPLETE")

    if not blocking_detail_codes and not missing:
        status = "ready"
        canonical_block = "CERT_OK"
    else:
        cd_status = _status_of(control_decision, "decision")
        status = "frozen" if cd_status == "freeze" else "blocked"
        first_detail = blocking_detail_codes[0] if blocking_detail_codes else "CERT_EVIDENCE_INDEX_INCOMPLETE"
        canonical_block = canonicalize_reason_code(first_detail)["canonical_category"]
        if canonical_block == "UNKNOWN":
            canonical_block = "CERTIFICATION_GAP"

    result = {
        "artifact_type": "certification_evidence_index",
        "schema_version": "1.0.0",
        "index_id": index_id,
        "trace_id": trace_id,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "blocking_reason_canonical": canonical_block,
        "blocking_detail_codes": blocking_detail_codes,
        "references": refs,
        "missing_references": missing,
        "freshness_status": freshness_status,
    }

    budget = enforce_proof_size_budget(proof_bundle={"index_refs": refs}, evidence_index=result, one_page_trace="")
    if budget["decision"] != "allow":
        result["status"] = "blocked"
        result["blocking_detail_codes"].append("CERT_INDEX_OVERSIZED_REFS")
        result["blocking_reason_canonical"] = "CERTIFICATION_GAP"

    result["delta_index"] = build_certification_delta(current_index=result, previous_index=previous_evidence_index)

    lines = [
        f"CERTIFICATION EVIDENCE INDEX — index_id={index_id} trace_id={trace_id}",
        f"status: {result['status']}",
        f"blocking_reason_canonical: {result['blocking_reason_canonical']}",
        f"freshness_status: {freshness_status}",
        "references:",
    ]
    for k, v in refs.items():
        lines.append(f"  {k}: {v or '-'}")
    if missing:
        lines.append(f"missing_references: {', '.join(missing)}")
    if blocking_detail_codes:
        lines.append(f"blocking_detail_codes: {', '.join(blocking_detail_codes)}")
    result["human_readable"] = "\n".join(lines)
    return result


__all__ = ["CertificationEvidenceIndexError", "OPTIONAL_REFERENCE_FIELDS", "REQUIRED_REFERENCE_FIELDS", "build_certification_evidence_index"]

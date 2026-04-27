"""Certification evidence index — reference-only packaging seam.

NS-10..12: Build a compact certification evidence index that points to the
evidence streams required for promotion. The index does NOT duplicate the
underlying artifacts — it only carries identifiers/refs and a status.

This module is a non-owning seam. It packages references into an index
artifact; canonical authority owners are unchanged. Status is computed
from the supplied evidence only:

  - ``ready``   when every required reference exists and all status fields
                report healthy/match/pass.
  - ``blocked`` when any required reference is missing or its status fails.
  - ``frozen``  when status indicates an upstream freeze.

Canonical blocking categories come from the canonical reason-code mapping.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from spectrum_systems.modules.observability.reason_code_canonicalizer import (
    canonicalize_reason_code,
)


REQUIRED_REFERENCE_FIELDS = (
    "eval_summary_ref",
    "lineage_summary_ref",
    "replay_summary_ref",
    "control_decision_ref",
    "authority_shape_preflight_ref",
    "registry_validation_ref",
    "artifact_tier_validation_ref",
)

OPTIONAL_REFERENCE_FIELDS = (
    "enforcement_action_ref",
    "failure_trace_ref",
)


class CertificationEvidenceIndexError(ValueError):
    """Raised when the evidence index cannot be deterministically constructed."""


def _ref_id(obj: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not isinstance(obj, Mapping):
        return None
    for key in (
        "artifact_id",
        "decision_id",
        "validation_id",
        "enforcement_id",
        "index_id",
        "trace_id",
        "id",
    ):
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
) -> Dict[str, Any]:
    """Build a certification_evidence_index artifact.

    The index is reference-only. It does not embed evidence; it embeds
    pointers (artifact_ids) and a derived status. Missing references are
    listed in ``missing_references`` and produce a ``blocked`` status.
    """
    if not isinstance(index_id, str) or not index_id.strip():
        raise CertificationEvidenceIndexError("index_id must be a non-empty string")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise CertificationEvidenceIndexError("trace_id must be a non-empty string")

    refs: Dict[str, Optional[str]] = {
        "eval_summary_ref": _ref_id(eval_summary),
        "lineage_summary_ref": _ref_id(lineage_summary),
        "replay_summary_ref": _ref_id(replay_summary),
        "control_decision_ref": _ref_id(control_decision),
        "enforcement_action_ref": _ref_id(enforcement_action) if state_changing else _ref_id(enforcement_action),
        "authority_shape_preflight_ref": _ref_id(authority_shape_preflight),
        "registry_validation_ref": _ref_id(registry_validation),
        "artifact_tier_validation_ref": _ref_id(artifact_tier_validation),
        "failure_trace_ref": _ref_id(failure_trace),
    }

    blocking_detail_codes: List[str] = []
    missing: List[str] = []

    # Required-reference completeness
    if eval_summary is None:
        missing.append("eval_summary_ref")
        blocking_detail_codes.append("CERT_MISSING_EVAL_PASS")
    else:
        eval_status = _status_of(eval_summary, "status", "coverage_completeness_status")
        if eval_status not in {"healthy", "complete", "pass", "ok"}:
            blocking_detail_codes.append("CERT_MISSING_EVAL_PASS")

    if lineage_summary is None:
        missing.append("lineage_summary_ref")
        blocking_detail_codes.append("CERT_MISSING_LINEAGE")
    else:
        lin_status = _status_of(lineage_summary, "status")
        if lin_status not in {"healthy", "ok"}:
            blocking_detail_codes.append("CERT_MISSING_LINEAGE")

    if replay_summary is None:
        missing.append("replay_summary_ref")
        blocking_detail_codes.append("CERT_MISSING_REPLAY_READINESS")
    else:
        rep_status = _status_of(replay_summary, "status")
        if rep_status not in {"healthy", "ok", "match"}:
            blocking_detail_codes.append("CERT_MISSING_REPLAY_READINESS")

    if control_decision is None:
        missing.append("control_decision_ref")
        blocking_detail_codes.append("CERT_MISSING_CONTROL_DECISION")
    else:
        cd = _status_of(control_decision, "decision")
        if cd == "freeze":
            blocking_detail_codes.append("CERT_MISSING_CONTROL_DECISION")
        elif cd != "allow":
            blocking_detail_codes.append("CERT_MISSING_CONTROL_DECISION")

    if state_changing and enforcement_action is None:
        missing.append("enforcement_action_ref")
        blocking_detail_codes.append("CERT_MISSING_ENFORCEMENT_RECORD")

    if authority_shape_preflight is None:
        missing.append("authority_shape_preflight_ref")
        blocking_detail_codes.append("CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT")
    else:
        ap_status = _status_of(
            authority_shape_preflight, "status", "preflight_status"
        )
        if ap_status != "pass":
            blocking_detail_codes.append("CERT_MISSING_AUTHORITY_SHAPE_PREFLIGHT")

    if registry_validation is None:
        missing.append("registry_validation_ref")
        blocking_detail_codes.append("CERT_REGISTRY_VIOLATION_PRESENT")
    else:
        rv_status = _status_of(registry_validation, "status")
        rv_violations = registry_validation.get("violations") if isinstance(registry_validation, Mapping) else None
        if rv_status not in {"pass", "ok", "healthy"} or (
            isinstance(rv_violations, list) and len(rv_violations) > 0
        ):
            blocking_detail_codes.append("CERT_REGISTRY_VIOLATION_PRESENT")

    if artifact_tier_validation is None:
        missing.append("artifact_tier_validation_ref")
        blocking_detail_codes.append("CERT_EVIDENCE_INDEX_INCOMPLETE")
    else:
        av_decision = _status_of(artifact_tier_validation, "decision")
        if av_decision != "allow":
            blocking_detail_codes.append("CERT_EVIDENCE_INDEX_INCOMPLETE")

    # Derive overall status
    if not blocking_detail_codes and not missing:
        status = "ready"
        canonical_block = "CERT_OK"
    else:
        # Detect freeze propagation from control_decision
        cd_status = _status_of(control_decision, "decision")
        status = "frozen" if cd_status == "freeze" else "blocked"
        # Map first detail code to canonical category
        first_detail = blocking_detail_codes[0] if blocking_detail_codes else "CERT_EVIDENCE_INDEX_INCOMPLETE"
        canon = canonicalize_reason_code(first_detail)
        canonical_block = canon["canonical_category"]
        if canonical_block == "UNKNOWN":
            canonical_block = "CERTIFICATION_GAP"

    human_lines = [
        f"CERTIFICATION EVIDENCE INDEX — index_id={index_id} trace_id={trace_id}",
        f"status: {status}",
        f"blocking_reason_canonical: {canonical_block}",
        "references:",
    ]
    for k, v in refs.items():
        human_lines.append(f"  {k}: {v or '-'}")
    if missing:
        human_lines.append(f"missing_references: {', '.join(missing)}")
    if blocking_detail_codes:
        human_lines.append(f"blocking_detail_codes: {', '.join(blocking_detail_codes)}")

    return {
        "artifact_type": "certification_evidence_index",
        "schema_version": "1.0.0",
        "index_id": index_id,
        "trace_id": trace_id,
        "status": status,
        "blocking_reason_canonical": canonical_block,
        "blocking_detail_codes": blocking_detail_codes,
        "references": refs,
        "missing_references": missing,
        "human_readable": "\n".join(human_lines),
    }


__all__ = [
    "CertificationEvidenceIndexError",
    "OPTIONAL_REFERENCE_FIELDS",
    "REQUIRED_REFERENCE_FIELDS",
    "build_certification_evidence_index",
]

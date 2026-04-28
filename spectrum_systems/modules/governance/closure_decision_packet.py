"""OC-10..12: Closure decision packet (non-owning support seam).

Packages the evidence required for CDE to render a closure decision.
The packet itself is a non-owning support seam that derives a
``packet_status`` deterministically from the supplied evidence
references:

  * ``ready_to_merge`` — every required evidence ref present and each
    referenced status reports healthy / ready / pass / aligned /
    sufficient.
  * ``not_ready``     — at least one required evidence is missing or
    its status is non-blocking but not yet ready (e.g. work selection
    still ``no_recommendation``).
  * ``freeze``        — any input reports a freeze (proof intake,
    bottleneck classifier, dashboard projection, fast trust gate,
    certification delta, trust regression).
  * ``blocked``       — any input reports an outright block.
  * ``unknown``       — required evidence inputs are absent.

Required evidence keys:

  * proof_intake_ref
  * bottleneck_classification_ref
  * dashboard_projection_ref
  * fast_trust_gate_ref
  * certification_delta_proof_ref
  * trust_regression_pack_ref
  * lineage_chain_ref

Module is non-owning. Canonical authority unchanged: CDE retains
closure verdict authority. This packet is a non-authority bundle that
makes CDE's job auditable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional


REQUIRED_EVIDENCE_KEYS = (
    "proof_intake_ref",
    "bottleneck_classification_ref",
    "dashboard_projection_ref",
    "fast_trust_gate_ref",
    "certification_delta_proof_ref",
    "trust_regression_pack_ref",
    "lineage_chain_ref",
)


CANONICAL_REASON_CODES = frozenset(
    {
        "CLOSURE_PACKET_READY",
        "CLOSURE_PACKET_NOT_READY",
        "CLOSURE_PACKET_BLOCKED",
        "CLOSURE_PACKET_FROZEN",
        "CLOSURE_PACKET_UNKNOWN",
        "CLOSURE_PACKET_MISSING_EVIDENCE",
        "CLOSURE_PACKET_PROOF_INTAKE_BLOCKED",
        "CLOSURE_PACKET_BOTTLENECK_BLOCKED",
        "CLOSURE_PACKET_DASHBOARD_DRIFT",
        "CLOSURE_PACKET_FAST_GATE_INSUFFICIENT",
        "CLOSURE_PACKET_CERTIFICATION_NOT_READY",
        "CLOSURE_PACKET_TRUST_REGRESSION_FAILED",
        "CLOSURE_PACKET_LINEAGE_GAP",
    }
)


class ClosureDecisionPacketError(ValueError):
    """Raised when the packet cannot be deterministically constructed."""


def _ref(obj: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not isinstance(obj, Mapping):
        return None
    for key in (
        "intake_id",
        "classification_id",
        "projection_id",
        "manifest_id",
        "run_id",
        "delta_id",
        "pack_id",
        "lineage_id",
        "artifact_id",
        "id",
    ):
        v = obj.get(key)
        if isinstance(v, str) and v.strip():
            return v
    return None


def _is_blocking_status(status: Optional[str]) -> bool:
    if not status:
        return True  # missing status is blocking
    return status not in (
        "ok",
        "ready",
        "pass",
        "passing",
        "selected",
        "aligned",
        "sufficient",
        "healthy",
    )


def _is_freeze(obj: Optional[Mapping[str, Any]]) -> bool:
    if not isinstance(obj, Mapping):
        return False
    for key in ("packet_status", "overall_status", "final_status", "status", "next_safe_action"):
        v = obj.get(key)
        if isinstance(v, str) and v.lower() in ("freeze", "frozen"):
            return True
    return False


def build_closure_decision_packet(
    *,
    packet_id: str,
    trace_id: str,
    audit_timestamp: str,
    proof_intake: Optional[Mapping[str, Any]] = None,
    bottleneck_classification: Optional[Mapping[str, Any]] = None,
    dashboard_projection: Optional[Mapping[str, Any]] = None,
    fast_trust_gate: Optional[Mapping[str, Any]] = None,
    certification_delta_proof: Optional[Mapping[str, Any]] = None,
    trust_regression_pack: Optional[Mapping[str, Any]] = None,
    lineage_chain: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a closure decision packet from the supplied evidence."""
    if not isinstance(packet_id, str) or not packet_id.strip():
        raise ClosureDecisionPacketError("packet_id must be a non-empty string")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise ClosureDecisionPacketError("trace_id must be a non-empty string")
    if not isinstance(audit_timestamp, str) or not audit_timestamp.strip():
        raise ClosureDecisionPacketError(
            "audit_timestamp must be a non-empty string"
        )

    refs = {
        "proof_intake_ref": _ref(proof_intake),
        "bottleneck_classification_ref": _ref(bottleneck_classification),
        "dashboard_projection_ref": _ref(dashboard_projection),
        "fast_trust_gate_ref": _ref(fast_trust_gate),
        "certification_delta_proof_ref": _ref(certification_delta_proof),
        "trust_regression_pack_ref": _ref(trust_regression_pack),
        "lineage_chain_ref": _ref(lineage_chain),
    }

    missing = [k for k in REQUIRED_EVIDENCE_KEYS if refs[k] is None]
    blocking_findings: List[Dict[str, Any]] = []

    # Detect freeze inputs
    freeze_inputs = [
        ("proof_intake_ref", proof_intake),
        ("bottleneck_classification_ref", bottleneck_classification),
        ("dashboard_projection_ref", dashboard_projection),
        ("fast_trust_gate_ref", fast_trust_gate),
        ("certification_delta_proof_ref", certification_delta_proof),
        ("trust_regression_pack_ref", trust_regression_pack),
    ]

    saw_freeze = any(_is_freeze(obj) for _, obj in freeze_inputs)

    # Map of (input, blocking_reason_code, status_keys, evidence_key)
    block_map = (
        ("proof_intake_ref", proof_intake, "CLOSURE_PACKET_PROOF_INTAKE_BLOCKED",
         ("overall_status",)),
        ("bottleneck_classification_ref", bottleneck_classification,
         "CLOSURE_PACKET_BOTTLENECK_BLOCKED", ("category",)),
        ("dashboard_projection_ref", dashboard_projection,
         "CLOSURE_PACKET_DASHBOARD_DRIFT", ("alignment_status",)),
        ("fast_trust_gate_ref", fast_trust_gate,
         "CLOSURE_PACKET_FAST_GATE_INSUFFICIENT", ("overall_status", "sufficiency")),
        ("certification_delta_proof_ref", certification_delta_proof,
         "CLOSURE_PACKET_CERTIFICATION_NOT_READY", ("status", "readiness_status")),
        ("trust_regression_pack_ref", trust_regression_pack,
         "CLOSURE_PACKET_TRUST_REGRESSION_FAILED", ("status", "overall_status")),
        ("lineage_chain_ref", lineage_chain,
         "CLOSURE_PACKET_LINEAGE_GAP", ("status", "overall_status")),
    )

    for evidence_key, obj, reason, status_keys in block_map:
        if not isinstance(obj, Mapping):
            continue
        status = None
        for sk in status_keys:
            v = obj.get(sk)
            if isinstance(v, str) and v.strip():
                status = v.lower()
                break
        # bottleneck_classification has no overall_status; treat
        # any category other than `none` (no current bottleneck) as
        # blocking unless next_safe_action is `warn`.
        if evidence_key == "bottleneck_classification_ref":
            cat = obj.get("category")
            action_obj = obj.get("next_safe_action") or {}
            action = (
                action_obj.get("action")
                if isinstance(action_obj, Mapping)
                else None
            )
            if cat in (None, "none"):
                continue
            if action == "warn":
                continue
            blocking_findings.append(
                {
                    "evidence_key": evidence_key,
                    "reason_code": reason,
                    "severity": "block" if action != "freeze" else "freeze",
                }
            )
            continue
        if status is None:
            blocking_findings.append(
                {
                    "evidence_key": evidence_key,
                    "reason_code": "CLOSURE_PACKET_MISSING_EVIDENCE",
                    "severity": "block",
                }
            )
            continue
        if status in ("freeze", "frozen"):
            blocking_findings.append(
                {
                    "evidence_key": evidence_key,
                    "reason_code": reason,
                    "severity": "freeze",
                }
            )
        elif _is_blocking_status(status):
            blocking_findings.append(
                {
                    "evidence_key": evidence_key,
                    "reason_code": reason,
                    "severity": "block",
                }
            )

    # If any required evidence ref is missing, that is also a blocker.
    for k in missing:
        blocking_findings.append(
            {
                "evidence_key": k,
                "reason_code": "CLOSURE_PACKET_MISSING_EVIDENCE",
                "severity": "block",
            }
        )

    if not refs.values() or all(v is None for v in refs.values()):
        packet_status = "unknown"
        reason_code = "CLOSURE_PACKET_UNKNOWN"
    elif saw_freeze or any(f.get("severity") == "freeze" for f in blocking_findings):
        packet_status = "freeze"
        reason_code = "CLOSURE_PACKET_FROZEN"
    elif blocking_findings:
        # If only block-severity findings, check whether they are
        # exclusively "missing" (not_ready) or include hard-block.
        only_missing = all(
            f.get("reason_code") == "CLOSURE_PACKET_MISSING_EVIDENCE"
            for f in blocking_findings
        )
        if only_missing and missing:
            packet_status = "not_ready"
            reason_code = "CLOSURE_PACKET_NOT_READY"
        else:
            packet_status = "blocked"
            # Pick the first non-missing reason code as primary
            primary = next(
                (
                    f.get("reason_code")
                    for f in blocking_findings
                    if f.get("reason_code") != "CLOSURE_PACKET_MISSING_EVIDENCE"
                ),
                "CLOSURE_PACKET_BLOCKED",
            )
            reason_code = primary
    else:
        packet_status = "ready_to_merge"
        reason_code = "CLOSURE_PACKET_READY"

    return {
        "artifact_type": "closure_decision_packet",
        "schema_version": "1.0.0",
        "packet_id": packet_id,
        "trace_id": trace_id,
        "audit_timestamp": audit_timestamp,
        "packet_status": packet_status,
        "reason_code": reason_code,
        "evidence": refs,
        "missing_evidence": missing,
        "blocking_findings": blocking_findings,
        "non_authority_assertions": [
            "preparatory_only",
            "not_control_authority",
            "not_certification_authority",
            "not_promotion_authority",
            "not_enforcement_authority",
            "not_closure_authority",
        ],
    }

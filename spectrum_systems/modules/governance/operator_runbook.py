"""OC-22..24: Operator runbook generator (evidence-bound).

Produces short runbook entries from existing proof and closure evidence.
The generator NEVER invents rationale. Every claim must point to an
existing artifact reference; if proof is insufficient, stale, or
conflicting, the entry is forced to ``insufficient_evidence`` and the
``next_safe_action`` becomes ``investigate``.

Inputs are dict-like:

  * ``proof_intake``                 — proof_intake_index
  * ``bottleneck_classification``    — bottleneck_classification
  * ``dashboard_projection``         — dashboard_truth_projection
  * ``closure_packet``               — closure_decision_packet
  * ``operational_closure_bundle``   — operational_closure_bundle (optional)

Module is non-owning. Canonical authority unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional


CANONICAL_REASON_CODES = frozenset(
    {
        "RUNBOOK_OK",
        "RUNBOOK_INSUFFICIENT_EVIDENCE",
        "RUNBOOK_STALE_EVIDENCE",
        "RUNBOOK_CONFLICTING_EVIDENCE",
        "RUNBOOK_BLOCKED_NO_INPUT",
    }
)


class OperatorRunbookError(ValueError):
    """Raised when a runbook entry cannot be deterministically built."""


def _ref(obj: Optional[Mapping[str, Any]], *keys: str) -> Optional[str]:
    if not isinstance(obj, Mapping):
        return None
    for k in keys or (
        "intake_id",
        "classification_id",
        "projection_id",
        "packet_id",
        "bundle_id",
        "id",
    ):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None


def _stale_or_conflict(intake: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not isinstance(intake, Mapping):
        return None
    overall = intake.get("overall_status")
    if overall == "blocked":
        rc = intake.get("reason_code")
        if isinstance(rc, str) and "STALE" in rc:
            return "stale"
        if isinstance(rc, str) and "CONFLICT" in rc:
            return "conflict"
    selections = intake.get("selections") or {}
    if isinstance(selections, Mapping):
        for v in selections.values():
            if not isinstance(v, Mapping):
                continue
            status = v.get("selection_status")
            if status == "stale":
                return "stale"
            if status == "conflict":
                return "conflict"
    return None


def build_operator_runbook_entry(
    *,
    entry_id: str,
    audit_timestamp: str,
    proof_intake: Optional[Mapping[str, Any]] = None,
    bottleneck_classification: Optional[Mapping[str, Any]] = None,
    dashboard_projection: Optional[Mapping[str, Any]] = None,
    closure_packet: Optional[Mapping[str, Any]] = None,
    operational_closure_bundle: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise OperatorRunbookError("entry_id must be a non-empty string")
    if not isinstance(audit_timestamp, str) or not audit_timestamp.strip():
        raise OperatorRunbookError(
            "audit_timestamp must be a non-empty string"
        )

    inputs_provided = [
        x is not None
        for x in (
            proof_intake,
            bottleneck_classification,
            dashboard_projection,
            closure_packet,
            operational_closure_bundle,
        )
    ]
    if not any(inputs_provided):
        return {
            "artifact_type": "operator_runbook_entry",
            "schema_version": "1.0.0",
            "entry_id": entry_id,
            "audit_timestamp": audit_timestamp,
            "status": "blocked",
            "summary": "no proof inputs supplied; refusing confident guidance",
            "claims": [],
            "next_safe_action": "investigate",
            "refused_claims": [
                {
                    "claim_text": "system status",
                    "reason_code": "RUNBOOK_BLOCKED_NO_INPUT",
                }
            ],
            "non_authority_assertions": [
                "advisory_only",
                "preparatory_only",
                "not_control_authority",
                "not_certification_authority",
                "not_enforcement_authority",
            ],
        }

    stale_or_conflict = _stale_or_conflict(proof_intake)
    if stale_or_conflict is not None:
        rc = (
            "RUNBOOK_STALE_EVIDENCE"
            if stale_or_conflict == "stale"
            else "RUNBOOK_CONFLICTING_EVIDENCE"
        )
        return {
            "artifact_type": "operator_runbook_entry",
            "schema_version": "1.0.0",
            "entry_id": entry_id,
            "audit_timestamp": audit_timestamp,
            "status": "insufficient_evidence",
            "summary": f"proof intake reports {stale_or_conflict} evidence; refusing confident guidance",
            "claims": [],
            "next_safe_action": "investigate",
            "refused_claims": [
                {
                    "claim_text": "system status",
                    "reason_code": rc,
                }
            ],
            "non_authority_assertions": [
                "advisory_only",
                "preparatory_only",
                "not_control_authority",
                "not_certification_authority",
                "not_enforcement_authority",
            ],
        }

    claims: List[Dict[str, str]] = []

    # Build claims only where we have evidence
    if isinstance(operational_closure_bundle, Mapping):
        ref = _ref(operational_closure_bundle)
        status = operational_closure_bundle.get("overall_status") or "unknown"
        if ref:
            claims.append(
                {
                    "claim_text": f"operational closure bundle status: {status}",
                    "evidence_ref": ref,
                    "evidence_kind": "operational_closure_bundle",
                }
            )

    if isinstance(closure_packet, Mapping):
        ref = _ref(closure_packet)
        ps = closure_packet.get("packet_status") or "unknown"
        if ref:
            claims.append(
                {
                    "claim_text": f"closure packet status: {ps}",
                    "evidence_ref": ref,
                    "evidence_kind": "closure_decision_packet",
                }
            )

    if isinstance(bottleneck_classification, Mapping):
        ref = _ref(bottleneck_classification)
        cat = bottleneck_classification.get("category") or "unknown"
        owner = bottleneck_classification.get("owning_system") or "?"
        if ref:
            claims.append(
                {
                    "claim_text": f"bottleneck category: {cat} (owner: {owner})",
                    "evidence_ref": ref,
                    "evidence_kind": "bottleneck_classification",
                }
            )

    if isinstance(dashboard_projection, Mapping):
        ref = _ref(dashboard_projection)
        align = dashboard_projection.get("alignment_status") or "unknown"
        if ref:
            claims.append(
                {
                    "claim_text": f"dashboard alignment: {align}",
                    "evidence_ref": ref,
                    "evidence_kind": "dashboard_truth_projection",
                }
            )

    if isinstance(proof_intake, Mapping):
        ref = _ref(proof_intake)
        overall = proof_intake.get("overall_status") or "unknown"
        if ref:
            claims.append(
                {
                    "claim_text": f"proof intake: {overall}",
                    "evidence_ref": ref,
                    "evidence_kind": "proof_intake_index",
                }
            )

    if not claims:
        return {
            "artifact_type": "operator_runbook_entry",
            "schema_version": "1.0.0",
            "entry_id": entry_id,
            "audit_timestamp": audit_timestamp,
            "status": "insufficient_evidence",
            "summary": "no evidence ids found in supplied inputs; refusing confident guidance",
            "claims": [],
            "next_safe_action": "investigate",
            "refused_claims": [
                {
                    "claim_text": "system status",
                    "reason_code": "RUNBOOK_INSUFFICIENT_EVIDENCE",
                }
            ],
            "non_authority_assertions": [
                "advisory_only",
                "preparatory_only",
                "not_control_authority",
                "not_certification_authority",
                "not_enforcement_authority",
            ],
        }

    # Derive status from the strongest available evidence in this
    # priority order: bundle -> closure packet -> classifier action
    status = "pass"
    next_action = "merge"
    summary_parts: List[str] = []
    if isinstance(operational_closure_bundle, Mapping):
        s = operational_closure_bundle.get("overall_status")
        if s in ("pass", "block", "freeze", "unknown"):
            status = s
            summary_parts.append(f"closure_bundle.overall_status={s}")
    if isinstance(closure_packet, Mapping):
        ps = closure_packet.get("packet_status")
        if ps == "freeze":
            status = "freeze"
        elif ps in ("blocked",):
            status = "block"
        elif ps in ("not_ready",) and status == "pass":
            status = "block"
        elif ps == "unknown" and status == "pass":
            status = "unknown"
    if isinstance(bottleneck_classification, Mapping):
        action_obj = bottleneck_classification.get("next_safe_action") or {}
        action = (
            action_obj.get("action")
            if isinstance(action_obj, Mapping)
            else None
        )
        if action == "freeze":
            status = "freeze"
            next_action = "freeze"
        elif action == "block":
            if status == "pass":
                status = "block"
            next_action = "investigate_bottleneck"

    if status == "pass":
        next_action = "merge"
    elif status == "freeze":
        next_action = "freeze"
    else:
        next_action = "investigate"

    summary = "; ".join(summary_parts) or f"derived status: {status}"

    return {
        "artifact_type": "operator_runbook_entry",
        "schema_version": "1.0.0",
        "entry_id": entry_id,
        "audit_timestamp": audit_timestamp,
        "status": status,
        "summary": summary,
        "claims": claims,
        "next_safe_action": next_action,
        "refused_claims": [],
        "non_authority_assertions": [
            "advisory_only",
            "preparatory_only",
            "not_control_authority",
            "not_certification_authority",
            "not_enforcement_authority",
        ],
    }

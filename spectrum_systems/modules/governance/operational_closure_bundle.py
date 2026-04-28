"""OC-25..27: Operational closure bundle (final reference-only summary).

Single bundle that answers the eight operator questions:

  1. Is the system pass / block / freeze / unknown?
  2. What is the current bottleneck?
  3. Which existing 3-letter system owns it?
  4. What proof artifact supports this?
  5. Is the dashboard / public surface aligned with repo truth?
  6. Is the fast trust gate sufficient?
  7. What is the next work item?
  8. What failure or measurable signal justifies that work?

The bundle is reference-only: every field is derived from supplied
evidence inputs. If evidence is missing, the field is null and the
overall_status falls back to ``unknown`` so a freshly arrived operator
cannot mistake silence for success.

Module is non-owning. Canonical authority unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


CANONICAL_REASON_CODES = frozenset(
    {
        "OPERATIONAL_CLOSURE_OK",
        "OPERATIONAL_CLOSURE_BLOCKED",
        "OPERATIONAL_CLOSURE_FROZEN",
        "OPERATIONAL_CLOSURE_UNKNOWN",
        "OPERATIONAL_CLOSURE_INSUFFICIENT_INPUTS",
    }
)


class OperationalClosureBundleError(ValueError):
    """Raised when the bundle cannot be deterministically constructed."""


def _ref(obj: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not isinstance(obj, Mapping):
        return None
    for k in (
        "intake_id",
        "classification_id",
        "projection_id",
        "packet_id",
        "manifest_id",
        "run_id",
        "record_id",
        "entry_id",
        "id",
    ):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None


def _truthy(s: Any) -> Optional[str]:
    if isinstance(s, str) and s.strip():
        return s
    return None


def build_operational_closure_bundle(
    *,
    bundle_id: str,
    audit_timestamp: str,
    proof_intake: Optional[Mapping[str, Any]] = None,
    bottleneck_classification: Optional[Mapping[str, Any]] = None,
    dashboard_projection: Optional[Mapping[str, Any]] = None,
    closure_packet: Optional[Mapping[str, Any]] = None,
    fast_trust_gate_run: Optional[Mapping[str, Any]] = None,
    work_selection_record: Optional[Mapping[str, Any]] = None,
    operator_runbook_entry: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(bundle_id, str) or not bundle_id.strip():
        raise OperationalClosureBundleError(
            "bundle_id must be a non-empty string"
        )
    if not isinstance(audit_timestamp, str) or not audit_timestamp.strip():
        raise OperationalClosureBundleError(
            "audit_timestamp must be a non-empty string"
        )

    # Refs
    refs = {
        "proof_intake_ref": _ref(proof_intake),
        "bottleneck_classification_ref": _ref(bottleneck_classification),
        "dashboard_projection_ref": _ref(dashboard_projection),
        "closure_packet_ref": _ref(closure_packet),
        "fast_trust_gate_ref": _ref(fast_trust_gate_run),
        "work_selection_ref": _ref(work_selection_record),
        "operator_runbook_ref": _ref(operator_runbook_entry),
    }

    # Bottleneck
    cat = "unknown"
    bottleneck_reason = "OPERATIONAL_CLOSURE_UNKNOWN"
    owning_system: Optional[str] = None
    if isinstance(bottleneck_classification, Mapping):
        cat = _truthy(bottleneck_classification.get("category")) or "unknown"
        bottleneck_reason = (
            _truthy(bottleneck_classification.get("reason_code"))
            or "OPERATIONAL_CLOSURE_UNKNOWN"
        )
        owning_system = _truthy(bottleneck_classification.get("owning_system"))

    # Supporting proof ref: prefer dashboard projection's latest_proof_ref,
    # else closure packet's evidence proof_intake_ref.
    supporting_proof_ref: Optional[str] = None
    if isinstance(dashboard_projection, Mapping):
        supporting_proof_ref = _truthy(
            dashboard_projection.get("latest_proof_ref")
        )
    if supporting_proof_ref is None and isinstance(closure_packet, Mapping):
        ev = closure_packet.get("evidence")
        if isinstance(ev, Mapping):
            supporting_proof_ref = _truthy(ev.get("proof_intake_ref"))

    # Dashboard alignment
    dashboard_alignment = "unknown"
    if isinstance(dashboard_projection, Mapping):
        dashboard_alignment = (
            _truthy(dashboard_projection.get("alignment_status")) or "unknown"
        )

    # Fast trust gate sufficiency
    fast_sufficiency = "unknown"
    if isinstance(fast_trust_gate_run, Mapping):
        s = _truthy(fast_trust_gate_run.get("sufficiency"))
        if s in ("sufficient", "insufficient"):
            fast_sufficiency = s
        else:
            overall = _truthy(fast_trust_gate_run.get("overall_status"))
            if overall == "ok":
                fast_sufficiency = "sufficient"
            elif overall in ("failed", "unknown"):
                fast_sufficiency = "insufficient"

    # Work item
    next_work = {"work_item_id": None, "selection_status": "unknown"}
    if isinstance(work_selection_record, Mapping):
        next_work = {
            "work_item_id": _truthy(
                work_selection_record.get("recommended_work_item_id")
            ),
            "selection_status": _truthy(
                work_selection_record.get("selection_status")
            )
            or "unknown",
        }

    # Justifying signal/failure
    justifying = "unknown"
    if isinstance(work_selection_record, Mapping):
        cands = work_selection_record.get("candidates") or []
        if isinstance(cands, list):
            for c in cands:
                if not isinstance(c, Mapping):
                    continue
                if c.get("accepted"):
                    justifying = (
                        _truthy(c.get("justification_kind")) or "unknown"
                    )
                    break
    if justifying == "unknown" and isinstance(bottleneck_classification, Mapping):
        # If bottleneck exists, its category itself is the justifying signal.
        if cat != "unknown":
            justifying = f"bottleneck:{cat}"

    # Overall status: prefer closure packet status, then dashboard status.
    overall_status = "unknown"
    if isinstance(closure_packet, Mapping):
        ps = _truthy(closure_packet.get("packet_status"))
        if ps == "ready_to_merge":
            overall_status = "pass"
        elif ps == "freeze":
            overall_status = "freeze"
        elif ps in ("blocked", "not_ready"):
            overall_status = "block"
        elif ps == "unknown":
            overall_status = "unknown"
    if overall_status == "unknown" and isinstance(dashboard_projection, Mapping):
        ds = _truthy(dashboard_projection.get("current_status"))
        if ds in ("pass", "block", "freeze", "unknown"):
            overall_status = ds

    # If the fast gate is insufficient, demote pass to block.
    if overall_status == "pass" and fast_sufficiency == "insufficient":
        overall_status = "block"

    # If dashboard alignment is missing/corrupt/drifted, demote pass to block.
    if overall_status == "pass" and dashboard_alignment in (
        "missing",
        "corrupt",
        "drifted",
    ):
        overall_status = "block"

    operator_questions = {
        "is_pass_block_freeze_or_unknown": overall_status,
        "current_bottleneck_label": cat,
        "owning_three_letter_system": owning_system,
        "proof_artifact_label": supporting_proof_ref,
        "dashboard_aligned_with_repo_truth": (
            "yes" if dashboard_alignment == "aligned" else "no"
        ),
        "fast_trust_gate_sufficient": (
            "yes" if fast_sufficiency == "sufficient" else "no"
        ),
        "next_work_item_label": next_work["work_item_id"],
        "justifying_failure_or_signal": justifying,
    }

    return {
        "artifact_type": "operational_closure_bundle",
        "schema_version": "1.0.0",
        "bundle_id": bundle_id,
        "audit_timestamp": audit_timestamp,
        "overall_status": overall_status,
        "current_bottleneck": {
            "category": cat,
            "reason_code": bottleneck_reason,
        },
        "owning_system": owning_system,
        "supporting_proof_ref": supporting_proof_ref,
        "dashboard_alignment": dashboard_alignment,
        "fast_trust_gate_sufficiency": fast_sufficiency,
        "next_work_item": next_work,
        "justifying_signal_or_failure": justifying,
        "evidence_refs": refs,
        "operator_questions": operator_questions,
        "non_authority_assertions": [
            "preparatory_only",
            "advisory_only",
            "not_control_authority",
            "not_certification_authority",
            "not_promotion_authority",
            "not_enforcement_authority",
            "not_closure_authority",
        ],
    }

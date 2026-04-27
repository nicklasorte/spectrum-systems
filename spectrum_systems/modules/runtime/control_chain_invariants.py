"""Control-loop invariants: TPA → CDE → SEL handoff verification.

NX-16: This module provides a deterministic, fail-closed verifier for the
control chain that the existing runtime modules depend on. It does NOT
re-implement decision logic — it only asserts that the artifact chain is
internally consistent and that no protected authority was bypassed.

Invariants enforced:
  - SEL enforcement requires a CDE control decision reference.
  - CDE closure requires an EVL eval summary reference.
  - SEL must not allow_execution when CDE decision is block/freeze.
  - Promotion path must include certification record reference.
  - No state-changing path (allow_execution / promotion) without
    a complete decision/enforcement pair.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional


class ControlChainViolation(ValueError):
    """Raised on invariant violation in the control chain."""


CANONICAL_CONTROL_REASON_CODES = {
    "CONTROL_OK",
    "CONTROL_ENFORCEMENT_WITHOUT_DECISION",
    "CONTROL_DECISION_WITHOUT_EVAL_SUMMARY",
    "CONTROL_POLICY_BYPASS",
    "CONTROL_PROMOTION_WITHOUT_CERTIFICATION",
    "CONTROL_DECISION_ENFORCEMENT_MISMATCH",
    "CONTROL_TRACE_MISMATCH",
}


def verify_control_chain(
    *,
    eval_summary: Optional[Mapping[str, Any]],
    control_decision: Optional[Mapping[str, Any]],
    enforcement_action: Optional[Mapping[str, Any]],
    certification_record: Optional[Mapping[str, Any]] = None,
    require_certification: bool = False,
) -> Dict[str, Any]:
    """Verify the TPA/EVL → CDE → SEL invariant chain.

    Returns
    -------
    {"decision": "allow"|"block",
     "reason_code": canonical reason,
     "blocking_reasons": [str,...],
     "trace_id": str,
     "involved_artifacts": {"eval": id, "control": id, "enforcement": id, "certification": id}}
    """
    blocking: List[str] = []
    reason_code = "CONTROL_OK"

    if enforcement_action is not None and not isinstance(enforcement_action, Mapping):
        raise ControlChainViolation("enforcement_action must be a mapping or None")
    if control_decision is not None and not isinstance(control_decision, Mapping):
        raise ControlChainViolation("control_decision must be a mapping or None")
    if eval_summary is not None and not isinstance(eval_summary, Mapping):
        raise ControlChainViolation("eval_summary must be a mapping or None")
    if certification_record is not None and not isinstance(certification_record, Mapping):
        raise ControlChainViolation("certification_record must be a mapping or None")

    # Invariant: enforcement requires control decision reference.
    if enforcement_action is not None:
        decision_ref = (
            enforcement_action.get("input_decision_reference")
            or enforcement_action.get("decision_id")
            or enforcement_action.get("decision_ref")
        )
        if not isinstance(decision_ref, str) or not decision_ref.strip():
            blocking.append("enforcement action lacks input_decision_reference")
            reason_code = "CONTROL_ENFORCEMENT_WITHOUT_DECISION"
        else:
            cde_id = (
                control_decision.get("decision_id")
                if isinstance(control_decision, Mapping)
                else None
            )
            if cde_id and decision_ref != cde_id:
                blocking.append(
                    f"enforcement.input_decision_reference={decision_ref!r} does not match "
                    f"control_decision.decision_id={cde_id!r}"
                )
                reason_code = "CONTROL_DECISION_ENFORCEMENT_MISMATCH"

    # Invariant: control decision requires eval summary reference.
    if control_decision is not None:
        eval_ref = (
            control_decision.get("input_eval_summary_reference")
            or control_decision.get("eval_summary_id")
            or control_decision.get("eval_summary_ref")
        )
        if not isinstance(eval_ref, str) or not eval_ref.strip():
            blocking.append("control decision lacks input_eval_summary_reference")
            if reason_code == "CONTROL_OK":
                reason_code = "CONTROL_DECISION_WITHOUT_EVAL_SUMMARY"

    # Invariant: SEL allow_execution requires CDE decision = allow.
    if enforcement_action is not None and isinstance(control_decision, Mapping):
        sel_action = str(enforcement_action.get("enforcement_action") or "").lower()
        cde_decision = str(control_decision.get("decision") or "").lower()
        if sel_action in {"allow_execution", "allow"} and cde_decision in {
            "block",
            "deny",
            "freeze",
        }:
            blocking.append(
                f"SEL allow_execution while CDE decision={cde_decision!r} is a policy bypass"
            )
            reason_code = "CONTROL_POLICY_BYPASS"

    # Invariant: trace continuity across the chain.
    trace_ids = []
    for source in (eval_summary, control_decision, enforcement_action, certification_record):
        if isinstance(source, Mapping):
            tid = source.get("trace_id") or (
                source.get("trace") or {}).get("trace_id")
            if isinstance(tid, str) and tid:
                trace_ids.append(tid)
    if trace_ids and len(set(trace_ids)) > 1:
        blocking.append(
            f"trace continuity broken across control chain: {sorted(set(trace_ids))}"
        )
        if reason_code == "CONTROL_OK":
            reason_code = "CONTROL_TRACE_MISMATCH"

    # Invariant: promotion path requires certification record.
    if require_certification:
        if certification_record is None:
            blocking.append("promotion path requires a certification record")
            reason_code = "CONTROL_PROMOTION_WITHOUT_CERTIFICATION"
        else:
            cert_status = str(
                certification_record.get("status")
                or certification_record.get("certification_status")
                or certification_record.get("decision")
                or ""
            ).lower()
            if cert_status in {"deny", "block", "fail", "incomplete"}:
                blocking.append(
                    f"certification record status {cert_status!r} blocks promotion"
                )
                reason_code = "CONTROL_PROMOTION_WITHOUT_CERTIFICATION"

    decision = "allow" if not blocking else "block"
    trace_id = trace_ids[0] if trace_ids else ""
    involved = {
        "eval": (
            eval_summary.get("artifact_id") or eval_summary.get("coverage_run_id")
            if isinstance(eval_summary, Mapping)
            else None
        ),
        "control": (
            control_decision.get("decision_id") if isinstance(control_decision, Mapping) else None
        ),
        "enforcement": (
            enforcement_action.get("enforcement_id") or enforcement_action.get("enforcement_result_id")
            if isinstance(enforcement_action, Mapping)
            else None
        ),
        "certification": (
            certification_record.get("certification_id") or certification_record.get("artifact_id")
            if isinstance(certification_record, Mapping)
            else None
        ),
    }
    return {
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": blocking,
        "trace_id": trace_id,
        "involved_artifacts": involved,
    }


__all__ = [
    "CANONICAL_CONTROL_REASON_CODES",
    "ControlChainViolation",
    "verify_control_chain",
]

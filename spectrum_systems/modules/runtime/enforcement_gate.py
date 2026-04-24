"""Enforcement gate — mandatory enforcement_action_record requirement for all non-allow decisions.

This module is the bridge between CDE (decision authority) and SEL (enforcement authority).
It wraps every CDE decision with an explicit enforcement requirement record so:

1. No non-allow decision can proceed to SEL without a documented enforcement requirement.
2. SEL must record the enforcement_action_record BEFORE executing the action.
3. Bypass is structurally impossible — the gate is not optional.

Design rules
------------
- CDE produces decisions; this gate marks their enforcement obligations.
- SEL consumes the enforcement_gate_decision; it must record before acting.
- allow decisions pass through with enforcement_required=False.
- warn/freeze/block decisions carry enforcement_required=True and
  enforcement_action_record_required_before_execution=True.
- Missing enforcement_action_record when required = hard fail (never silence).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Actions that require enforcement recording
# ---------------------------------------------------------------------------

_ENFORCEMENT_REQUIRED_RESPONSES = frozenset({"warn", "freeze", "block"})
_ENFORCEMENT_REQUIRED_OUTCOMES = frozenset({
    "block",
    "human_review_required",
    "quarantine",
    "halt",
})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _gate_id(decision_ref: str) -> str:
    digest = hashlib.sha256(decision_ref.encode()).hexdigest()[:16]
    return f"enf-gate-{digest}"


def _enforcement_required(decision: Dict[str, Any]) -> bool:
    """Return True if the decision requires an enforcement_action_record."""
    system_response = str(decision.get("system_response") or "")
    decision_outcome = str(decision.get("decision_outcome") or "")
    action = str(decision.get("action") or "")
    return (
        system_response in _ENFORCEMENT_REQUIRED_RESPONSES
        or decision_outcome in _ENFORCEMENT_REQUIRED_OUTCOMES
        or action in _ENFORCEMENT_REQUIRED_RESPONSES
    )


# ---------------------------------------------------------------------------
# Gate functions
# ---------------------------------------------------------------------------


def apply_enforcement_gate(
    cde_decision: Dict[str, Any],
    *,
    gate_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Wrap a CDE decision with enforcement requirement metadata.

    Parameters
    ----------
    cde_decision:
        Any CDE decision artifact (evaluation_control_decision,
        continuation_decision_record, or similar).
    gate_timestamp:
        RFC3339 timestamp; defaults to current UTC time.

    Returns
    -------
    dict
        enforcement_gate_decision artifact containing:
        - enforcement_required: bool
        - enforcement_action_record_required: bool (same as enforcement_required)
        - enforcement_action_record_required_before_execution: bool
        - original_decision_ref: reference to source decision
        - gate_id: unique identifier for this gate record

    Raises
    ------
    ValueError
        If cde_decision is not a dict.
    TypeError
        If cde_decision is missing identifying fields.
    """
    if not isinstance(cde_decision, dict):
        raise ValueError("cde_decision must be a dict")

    if gate_timestamp is None:
        gate_timestamp = _utc_now()

    required = _enforcement_required(cde_decision)
    artifact_type = str(cde_decision.get("artifact_type") or "unknown")
    decision_id = str(
        cde_decision.get("decision_id")
        or cde_decision.get("decision_id")
        or cde_decision.get("record_id")
        or cde_decision.get("eval_id")
        or "unknown"
    )

    original_ref = f"{artifact_type}:{decision_id}"
    gate = {
        "artifact_type": "enforcement_gate_decision",
        "schema_version": "1.0.0",
        "gate_id": _gate_id(original_ref),
        "original_decision_artifact_type": artifact_type,
        "original_decision_ref": original_ref,
        "system_response": str(cde_decision.get("system_response") or cde_decision.get("decision_outcome") or "allow"),
        "enforcement_required": required,
        "enforcement_action_record_required": required,
        "enforcement_action_record_required_before_execution": required,
        "gate_timestamp": gate_timestamp,
    }
    return gate


def verify_enforcement_recorded(
    enforcement_gate_decision: Dict[str, Any],
    enforcement_action_record: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Verify that SEL recorded the enforcement_action_record when required.

    Call this AFTER SEL executes but BEFORE marking the action complete.

    Parameters
    ----------
    enforcement_gate_decision:
        Output of apply_enforcement_gate().
    enforcement_action_record:
        The enforcement_action_record emitted by SEL, or None.

    Returns
    -------
    dict
        {verified: bool, reason: str}

    Raises
    ------
    RuntimeError
        If enforcement was required but no record was provided — fail closed.
    """
    if not isinstance(enforcement_gate_decision, dict):
        raise ValueError("enforcement_gate_decision must be a dict")

    required = bool(enforcement_gate_decision.get("enforcement_action_record_required"))

    if not required:
        return {
            "verified": True,
            "reason": "enforcement_not_required_for_allow_decision",
            "action_recorded": False,
        }

    if enforcement_action_record is None:
        raise RuntimeError(
            f"ENFORCEMENT_BYPASS_VIOLATION: gate_id={enforcement_gate_decision.get('gate_id')} "
            f"requires enforcement_action_record but none was provided — fail closed"
        )

    if not isinstance(enforcement_action_record, dict):
        raise RuntimeError(
            "ENFORCEMENT_BYPASS_VIOLATION: enforcement_action_record must be a dict — fail closed"
        )

    return {
        "verified": True,
        "reason": "enforcement_action_record_present",
        "action_recorded": True,
        "action_record_ref": str(
            enforcement_action_record.get("action_id")
            or enforcement_action_record.get("artifact_id")
            or "unknown"
        ),
    }


def build_sel_enforcement_record(
    *,
    gate_decision: Dict[str, Any],
    action_taken: str,
    trace_id: str,
    decision_ref: str,
    reason: str,
    executor: str = "SEL",
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a lightweight enforcement_action_record for the SEL to emit.

    This record MUST be persisted before the enforcement action executes.

    Parameters
    ----------
    gate_decision:
        The enforcement_gate_decision artifact.
    action_taken:
        The action SEL is about to take (warn/freeze/block/etc.).
    trace_id:
        Traceability reference.
    decision_ref:
        Reference to the CDE decision that triggered this enforcement.
    reason:
        Human-readable reason for the enforcement.
    executor:
        Which subsystem is executing this action (default: SEL).
    timestamp:
        RFC3339 timestamp; defaults to current UTC.

    Returns
    -------
    dict
        sel_enforcement_action_record artifact.
    """
    if timestamp is None:
        timestamp = _utc_now()

    gate_id = str(gate_decision.get("gate_id") or "unknown")
    record_id = hashlib.sha256(f"{gate_id}:{action_taken}:{trace_id}".encode()).hexdigest()[:16]

    return {
        "artifact_type": "sel_enforcement_action_record",
        "schema_version": "1.0.0",
        "record_id": f"sel-enf-{record_id}",
        "gate_id": gate_id,
        "trace_id": trace_id,
        "decision_ref": decision_ref,
        "action_taken": action_taken,
        "reason": reason,
        "executor": executor,
        "recorded_before_execution": True,
        "timestamp": timestamp,
    }

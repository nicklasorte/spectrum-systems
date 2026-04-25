"""RFX decision-bridge guard — LOOP-04.

RFX (Review → Fix → eXecute) is a cross-system phase label. Canonical roles
are recorded in ``docs/architecture/system_registry.md``; this module does not
restate or redefine them. The guard verifies the fail-closed bridge between a
recorded closure decision and a recorded enforcement context.

Behavior is fail-closed:
  - missing closure decision           -> rfx_missing_cde_decision
  - invalid closure decision status    -> rfx_invalid_cde_decision
  - missing enforcement context        -> rfx_missing_sel_context
  - enforcement not linked to decision -> rfx_sel_not_linked_to_cde

No implicit closure derivation is permitted. This module is a non-owning
phase-label support helper.
"""

from __future__ import annotations

from typing import Any


class RFXDecisionBridgeGuardError(ValueError):
    """Raised when the RFX CDE→SEL decision-bridge invariants fail closed."""


_VALID_CDE_STATUSES = frozenset({"ready", "not_ready"})


def _coerce_decision_id(cde_decision: dict[str, Any]) -> str | None:
    for key in ("decision_id", "cde_decision_id", "id"):
        value = cde_decision.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _coerce_sel_link(sel_context: dict[str, Any]) -> str | None:
    for key in ("cde_decision_ref", "cde_decision_id", "decision_ref", "linked_cde_decision_id"):
        value = sel_context.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def assert_rfx_cde_sel_decision_bridge(
    *,
    cde_decision: dict[str, Any] | None,
    sel_context: dict[str, Any] | None,
) -> None:
    """Assert the CDE → SEL closure-to-enforcement bridge for RFX.

    Fails closed when the CDE decision is missing, when its status is outside
    the deterministic set ``{"ready", "not_ready"}``, when the SEL context is
    missing, or when the SEL context does not reference the CDE decision.
    """
    if not isinstance(cde_decision, dict) or not cde_decision:
        raise RFXDecisionBridgeGuardError(
            "rfx_missing_cde_decision: CDE closure decision absent — SEL enforcement blocked"
        )

    cde_status = cde_decision.get("status")
    if cde_status not in _VALID_CDE_STATUSES:
        raise RFXDecisionBridgeGuardError(
            f"rfx_invalid_cde_decision: cde_decision.status={cde_status!r} "
            f"not in {sorted(_VALID_CDE_STATUSES)!r}"
        )

    cde_decision_id = _coerce_decision_id(cde_decision)
    if cde_decision_id is None:
        raise RFXDecisionBridgeGuardError(
            "rfx_invalid_cde_decision: cde_decision missing decision_id — "
            "SEL cannot link to an unidentified CDE decision"
        )

    if not isinstance(sel_context, dict) or not sel_context:
        raise RFXDecisionBridgeGuardError(
            "rfx_missing_sel_context: SEL enforcement context absent — "
            "no enforcement may proceed without an SEL context bound to CDE"
        )

    sel_link = _coerce_sel_link(sel_context)
    if sel_link is None or sel_link != cde_decision_id:
        raise RFXDecisionBridgeGuardError(
            f"rfx_sel_not_linked_to_cde: sel_context cde_decision_ref={sel_link!r} "
            f"does not match cde_decision.decision_id={cde_decision_id!r}"
        )


__all__ = [
    "RFXDecisionBridgeGuardError",
    "assert_rfx_cde_sel_decision_bridge",
]

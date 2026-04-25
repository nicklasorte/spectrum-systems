"""RFX decision-to-enforcement linkage guard — LOOP-04 implementation.

This module is a non-owning linkage check used during the RFX phase. It
does not issue closure or enforcement decisions; canonical responsibilities
for those signals stay with the systems declared in the system registry.
The guard verifies that an enforcement-context record explicitly references
the closure-decision record supplied alongside it, so downstream actions
cannot proceed without a present and well-formed decision artifact.

Failure modes are deterministic and emit machine-readable reason codes.
Missing artifact = halt. Implicit closure is not permitted.
"""

from __future__ import annotations

from typing import Any


class RFXDecisionBridgeGuardError(ValueError):
    """Raised when the RFX decision-to-enforcement linkage guard fails closed."""


_VALID_CDE_STATUSES = frozenset({"ready", "not_ready"})


def _is_nonempty_dict(obj: Any) -> bool:
    return isinstance(obj, dict) and bool(obj)


def assert_rfx_cde_sel_decision_bridge(
    *,
    cde_decision: dict[str, Any] | None,
    sel_context: dict[str, Any] | None,
) -> None:
    """Verify an enforcement-context record references the closure-decision artifact.

    This guard does not issue closure or enforcement decisions. It checks
    presence and link integrity, then fails closed with deterministic,
    machine-readable reason codes when the link is missing or malformed.

    Fail-closed reason codes:
      - ``rfx_missing_cde_decision``: closure-decision record is absent or empty.
      - ``rfx_invalid_cde_decision``: closure-decision status is not in
        ``{ready, not_ready}``.
      - ``rfx_missing_sel_context``: enforcement-context record is absent or empty.
      - ``rfx_sel_not_linked_to_cde``: enforcement-context record does not
        reference the supplied closure-decision artifact (implicit closure is
        not permitted).
    """
    if not _is_nonempty_dict(cde_decision):
        raise RFXDecisionBridgeGuardError(
            "rfx_missing_cde_decision: closure-decision artifact absent — "
            "enforcement linkage cannot be verified without an explicit input"
        )

    cde_status = cde_decision.get("status")
    if cde_status not in _VALID_CDE_STATUSES:
        raise RFXDecisionBridgeGuardError(
            f"rfx_invalid_cde_decision: closure-decision status={cde_status!r} "
            f"not in {sorted(_VALID_CDE_STATUSES)}"
        )

    if not _is_nonempty_dict(sel_context):
        raise RFXDecisionBridgeGuardError(
            "rfx_missing_sel_context: enforcement-context record absent — "
            "cannot verify linkage from the closure-decision artifact"
        )

    cde_decision_id = cde_decision.get("decision_id")
    sel_cde_ref = sel_context.get("cde_decision_ref")
    sel_cde_id = sel_context.get("cde_decision_id")

    expected_ref = (
        f"cde_decision:{cde_decision_id}" if isinstance(cde_decision_id, str) and cde_decision_id else None
    )

    linked_by_ref = (
        expected_ref is not None
        and isinstance(sel_cde_ref, str)
        and sel_cde_ref == expected_ref
    )
    linked_by_id = (
        isinstance(cde_decision_id, str)
        and cde_decision_id
        and isinstance(sel_cde_id, str)
        and sel_cde_id == cde_decision_id
    )

    if not (linked_by_ref or linked_by_id):
        raise RFXDecisionBridgeGuardError(
            "rfx_sel_not_linked_to_cde: enforcement-context record does not "
            "reference the supplied closure-decision artifact (expected "
            f"cde_decision_ref={expected_ref!r} or "
            f"cde_decision_id={cde_decision_id!r}); implicit closure is not "
            "permitted"
        )


__all__ = [
    "RFXDecisionBridgeGuardError",
    "assert_rfx_cde_sel_decision_bridge",
]

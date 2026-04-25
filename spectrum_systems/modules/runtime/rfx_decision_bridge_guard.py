"""RFX decision bridge guard — LOOP-04 implementation.

RFX is a cross-system phase label. CDE remains the sole closure-decision
authority and SEL remains the sole enforcement authority. This guard does NOT
move closure authority and does NOT introduce a new RFX authority. It only
asserts that an SEL enforcement context is explicitly bridged from a present
and well-formed CDE closure decision.

Failure modes are deterministic and emit machine-readable reason codes.
Missing artifact = halt. No implicit closure permitted.
"""

from __future__ import annotations

from typing import Any


class RFXDecisionBridgeGuardError(ValueError):
    """Raised when RFX CDE -> SEL decision-bridge invariants fail closed."""


_VALID_CDE_STATUSES = frozenset({"ready", "not_ready"})


def _is_nonempty_dict(obj: Any) -> bool:
    return isinstance(obj, dict) and bool(obj)


def assert_rfx_cde_sel_decision_bridge(
    *,
    cde_decision: dict[str, Any] | None,
    sel_context: dict[str, Any] | None,
) -> None:
    """Assert SEL enforcement is explicitly bridged from a valid CDE decision.

    Fail-closed reason codes:
      - ``rfx_missing_cde_decision``: CDE closure decision is absent or empty.
      - ``rfx_invalid_cde_decision``: CDE decision status is not in
        ``{ready, not_ready}``.
      - ``rfx_missing_sel_context``: SEL enforcement context is absent or empty.
      - ``rfx_sel_not_linked_to_cde``: SEL context does not reference the
        provided CDE decision (no implicit closure allowed).
    """
    if not _is_nonempty_dict(cde_decision):
        raise RFXDecisionBridgeGuardError(
            "rfx_missing_cde_decision: CDE closure decision artifact absent — "
            "SEL enforcement cannot proceed without explicit CDE input"
        )

    cde_status = cde_decision.get("status")
    if cde_status not in _VALID_CDE_STATUSES:
        raise RFXDecisionBridgeGuardError(
            f"rfx_invalid_cde_decision: CDE decision status={cde_status!r} "
            f"not in {sorted(_VALID_CDE_STATUSES)}"
        )

    if not _is_nonempty_dict(sel_context):
        raise RFXDecisionBridgeGuardError(
            "rfx_missing_sel_context: SEL enforcement context absent — "
            "cannot bridge CDE decision to enforcement"
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
            "rfx_sel_not_linked_to_cde: SEL context does not reference the "
            "supplied CDE decision (expected cde_decision_ref="
            f"{expected_ref!r} or cde_decision_id={cde_decision_id!r}); "
            "no implicit closure permitted"
        )


__all__ = [
    "RFXDecisionBridgeGuardError",
    "assert_rfx_cde_sel_decision_bridge",
]

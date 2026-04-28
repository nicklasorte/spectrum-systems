"""RFX error-budget governance expansion — RFX-14.

Ties RFX expansion to reliability-budget posture. SLO retains all
reliability/error-budget authority recorded in
``docs/architecture/system_registry.md``; this module is a non-owning
phase-label support helper that consumes SLO evidence to gate which kind
of work may continue when the budget is exhausted.

Behavior:

  * If budget exhausted → new capability work is ineligible.
  * Only reliability/hardening work may continue.
  * Must consume SLO evidence rather than computing budget itself.

Reason codes:

  * ``rfx_error_budget_exhausted``
  * ``rfx_new_capability_frozen``
  * ``rfx_reliability_work_allowed``
  * ``rfx_budget_posture_missing``
"""

from __future__ import annotations

from typing import Any


class RFXErrorBudgetGovernanceError(ValueError):
    """Raised when the error-budget governance gate fails closed."""


_RELIABILITY_WORK_TYPES: frozenset[str] = frozenset(
    {"reliability", "hardening", "regression_fix", "telemetry", "replay_fix", "policy_hardening"}
)


def _coerce_str(record: dict[str, Any] | None, *keys: str) -> str | None:
    if not isinstance(record, dict):
        return None
    for k in keys:
        v = record.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _budget_exhausted(slo_posture: dict[str, Any]) -> bool:
    """Return True when SLO posture indicates exhausted budget.

    Accepts:

      * ``budget_exhausted`` boolean
      * ``budget_status`` in {exhausted, breached, frozen}
      * ``status`` / ``posture`` in {exhausted, breached, frozen}
    """
    if not isinstance(slo_posture, dict):
        return False
    explicit = _coerce_bool(slo_posture.get("budget_exhausted"))
    if explicit is not None:
        return explicit
    for k in ("budget_status", "status", "posture"):
        v = slo_posture.get(k)
        if isinstance(v, str) and v.strip().lower() in {"exhausted", "breached", "frozen"}:
            return True
    return False


def assert_rfx_error_budget_governance(
    *,
    slo_posture: dict[str, Any] | None,
    proposed_work: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assert error-budget governance for a proposed work item.

    ``proposed_work`` must include:

      * ``work_type`` — string; "reliability" or "capability" (or detailed
        equivalents such as ``regression_fix``, ``hardening``, etc.)
      * ``reliability_evidence_refs`` — list of refs proving reliability
        intent when ``work_type`` claims reliability/hardening

    Returns an ``rfx_error_budget_governance_record`` artifact with a
    deterministic eligibility outcome.
    """
    reasons: list[str] = []

    if not isinstance(slo_posture, dict) or not slo_posture:
        reasons.append(
            "rfx_budget_posture_missing: SLO posture record absent — "
            "RFX cannot determine error-budget eligibility without SLO evidence"
        )
    if not isinstance(proposed_work, dict) or not proposed_work:
        reasons.append(
            "rfx_budget_posture_missing: proposed_work mapping absent"
        )

    if reasons:
        raise RFXErrorBudgetGovernanceError("; ".join(reasons))

    work_type = _coerce_str(proposed_work, "work_type", "type")
    if work_type is None:
        raise RFXErrorBudgetGovernanceError(
            "rfx_budget_posture_missing: proposed_work.work_type absent"
        )

    is_reliability_work = work_type.lower() in _RELIABILITY_WORK_TYPES
    evidence_refs = proposed_work.get("reliability_evidence_refs") if isinstance(proposed_work, dict) else None
    if is_reliability_work:
        if not isinstance(evidence_refs, list) or not any(
            isinstance(r, str) and r.strip() for r in evidence_refs
        ):
            raise RFXErrorBudgetGovernanceError(
                "rfx_budget_posture_missing: reliability work declared without "
                "reliability_evidence_refs — cannot classify work as reliability/hardening"
            )

    exhausted = _budget_exhausted(slo_posture)

    outcome_signal_reason_codes: list[str] = []
    if exhausted:
        outcome_signal_reason_codes.append("rfx_error_budget_exhausted")
        if not is_reliability_work:
            outcome_signal_reason_codes.append("rfx_new_capability_frozen")
            eligibility = "blocked"
        else:
            outcome_signal_reason_codes.append("rfx_reliability_work_allowed")
            eligibility = "allowed_reliability_only"
    else:
        eligibility = "allowed"

    if eligibility == "blocked":
        # Surface the blocking reason as a fail-closed exception so callers
        # cannot accidentally advance new-capability work under exhausted
        # budget.
        raise RFXErrorBudgetGovernanceError(
            "; ".join(outcome_signal_reason_codes)
            + ": new capability work is ineligible while error budget is exhausted"
        )

    return {
        "artifact_type": "rfx_error_budget_governance_record",
        "schema_version": "1.0.0",
        "budget_exhausted": exhausted,
        "is_reliability_work": is_reliability_work,
        "eligibility": eligibility,
        "reason_codes": outcome_signal_reason_codes,
        "ownership_note": (
            "SLO retains reliability/error-budget authority; this record interprets posture only."
        ),
    }


__all__ = [
    "RFXErrorBudgetGovernanceError",
    "assert_rfx_error_budget_governance",
]

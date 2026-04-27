"""Control signal minimality audit (NT-16..18).

Audits a proposed control input bundle and asserts:

  - Only the canonical hard trust signals can drive freeze/block.
  - Non-trust observations (report counts, dashboard freshness, advisory
    recommendations, cosmetic formatting issues, non-critical trends)
    must NEVER produce a freeze/block decision unless explicitly promoted
    to a hard trust signal by policy.
  - Every block/freeze carries a canonical reason and points to evidence.

This is a non-owning seam. It does NOT decide promotion; it returns a
classification of which signals are hard-trust versus observation-only,
and it provides the canonical reason if the proposed control input
crosses the boundary.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional


# NT-16: hard trust signals are the only inputs that can drive
# freeze/block. They are kept in lock-step with
# ``slo_budget_gate.HARD_TRUST_SIGNALS`` and extended here with the
# freshness signal introduced by NT-01..03.
HARD_TRUST_SIGNAL_NAMES = (
    "required_eval_pass_status",
    "replay_match_status",
    "lineage_completeness_status",
    "context_admissibility_status",
    "authority_shape_preflight_status",
    "registry_validation_status",
    "certification_evidence_index_status",
    "artifact_tier_validity_status",
    "trust_artifact_freshness_status",
)


# NT-16: known observation-only signal names. Anything in this set is
# explicitly NOT promotion-gating; it may surface as a warn but never
# block/freeze.
OBSERVATION_ONLY_SIGNAL_NAMES = (
    "dashboard_freshness_seconds",
    "report_volume",
    "report_count",
    "advisory_recommendation_count",
    "non_critical_trend_score",
    "cosmetic_formatting_score",
    "render_latency_ms",
    "operator_friction_score",
)


CANONICAL_MINIMALITY_REASON_CODES = {
    "MINIMALITY_OK",
    "MINIMALITY_OBSERVATION_HIJACK",
    "MINIMALITY_UNKNOWN_SIGNAL",
    "MINIMALITY_MISSING_EVIDENCE_REF",
    "MINIMALITY_MISSING_CANONICAL_REASON",
}


class ControlSignalMinimalityError(ValueError):
    """Raised when minimality audit cannot be deterministically performed."""


def classify_signal(name: str) -> str:
    """Return ``"hard_trust"``, ``"observation"``, or ``"unknown"``."""
    if name in HARD_TRUST_SIGNAL_NAMES:
        return "hard_trust"
    if name in OBSERVATION_ONLY_SIGNAL_NAMES:
        return "observation"
    return "unknown"


def audit_control_signal_minimality(
    *,
    proposed_decision: Mapping[str, Any],
    signals_used: Mapping[str, Any],
    evidence_refs: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Audit a proposed control decision for signal minimality.

    Parameters
    ----------
    proposed_decision:
        Mapping with ``decision`` (allow|warn|freeze|block),
        ``canonical_reason`` (str), and any other surface fields.
    signals_used:
        Mapping of signal_name → value used to derive ``proposed_decision``.
    evidence_refs:
        Iterable of artifact IDs the decision points to. Required when
        proposed_decision.decision is ``freeze`` or ``block``.

    Returns a ``control_signal_minimality_audit`` artifact:
        {
          "artifact_type": "control_signal_minimality_audit",
          "decision": "allow"|"block",
          "reason_code": canonical,
          "blocking_reasons": [...],
          "hard_trust_used": [...],
          "observations_used": [...],
          "unknown_signals": [...],
        }
    """
    if not isinstance(proposed_decision, Mapping):
        raise ControlSignalMinimalityError("proposed_decision must be a mapping")
    if not isinstance(signals_used, Mapping):
        raise ControlSignalMinimalityError("signals_used must be a mapping")

    decision = str(proposed_decision.get("decision") or "").lower()
    canonical_reason = str(proposed_decision.get("canonical_reason") or "").strip()

    hard_trust_used: List[str] = []
    observations_used: List[str] = []
    unknown_signals: List[str] = []
    for name in signals_used:
        kind = classify_signal(str(name))
        if kind == "hard_trust":
            hard_trust_used.append(str(name))
        elif kind == "observation":
            observations_used.append(str(name))
        else:
            unknown_signals.append(str(name))

    blocking: List[str] = []
    audit_decision = "allow"
    audit_reason = "MINIMALITY_OK"

    def _block(reason: str, why: str) -> None:
        nonlocal audit_decision, audit_reason
        audit_decision = "block"
        if audit_reason == "MINIMALITY_OK":
            audit_reason = reason
        blocking.append(why)

    if decision in {"freeze", "block"}:
        # Must rest on at least one hard trust signal.
        if not hard_trust_used:
            _block(
                "MINIMALITY_OBSERVATION_HIJACK",
                f"decision={decision} relies on no hard trust signals; "
                f"observations_used={observations_used} unknown_signals={unknown_signals}",
            )
        # Must carry a canonical reason.
        if not canonical_reason:
            _block(
                "MINIMALITY_MISSING_CANONICAL_REASON",
                f"decision={decision} carries no canonical_reason",
            )
        # Must point to evidence.
        evidence_list = list(evidence_refs or [])
        if not any(isinstance(r, str) and r.strip() for r in evidence_list):
            _block(
                "MINIMALITY_MISSING_EVIDENCE_REF",
                f"decision={decision} provides no evidence_refs",
            )

    if unknown_signals:
        _block(
            "MINIMALITY_UNKNOWN_SIGNAL",
            f"signals not classified as hard_trust or observation: "
            f"{sorted(unknown_signals)}",
        )

    return {
        "artifact_type": "control_signal_minimality_audit",
        "schema_version": "1.0.0",
        "decision": audit_decision,
        "reason_code": audit_reason,
        "blocking_reasons": blocking,
        "hard_trust_used": sorted(set(hard_trust_used)),
        "observations_used": sorted(set(observations_used)),
        "unknown_signals": sorted(set(unknown_signals)),
        "input_decision": decision,
        "input_canonical_reason": canonical_reason,
    }


__all__ = [
    "CANONICAL_MINIMALITY_REASON_CODES",
    "ControlSignalMinimalityError",
    "HARD_TRUST_SIGNAL_NAMES",
    "OBSERVATION_ONLY_SIGNAL_NAMES",
    "audit_control_signal_minimality",
    "classify_signal",
]

"""RGE Trust Bootstrapper.

Tracks trust accrual for RGE-authored roadmap proposals. Trust is earned
through accepted recommendations; it is not configurable.

Modes:
  - shadow       (trust < SHADOW_TO_WARN_GATED)  -> queue for human; no execute
  - warn_gated   (trust >= SHADOW_TO_WARN_GATED) -> execute under warn_gate
  - autonomous   (trust >= WARN_GATED_TO_AUTO)   -> execute autonomously

Mode transitions must be witnessed by an adjudication bundle containing both a
CDE decision and a TPA record. Without both, the transition is blocked.

Every recommendation emits an `rge_trust_record`.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.contracts import validate_artifact

SHADOW_TO_WARN_GATED = 0.7
WARN_GATED_TO_AUTO = 0.9

_MODES = ("shadow", "warn_gated", "autonomous")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"TRR-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def _mode_for(score: float) -> str:
    if score >= WARN_GATED_TO_AUTO:
        return "autonomous"
    if score >= SHADOW_TO_WARN_GATED:
        return "warn_gated"
    return "shadow"


def _evidence_coverage_score(decisions: list[dict[str, Any]]) -> float:
    """Weighted accept rate over prior human/CDE decisions on RGE proposals.

    Each decision item may have: {"outcome": "accept"|"reject"|"override", ...}.
    Accept=1.0, override=0.5, reject=0.0. Empty history -> 0.0 (starts shadow).
    """
    if not decisions:
        return 0.0
    weights = {"accept": 1.0, "override": 0.5, "reject": 0.0}
    total = 0.0
    n = 0
    for d in decisions:
        outcome = str(d.get("outcome", "")).lower()
        if outcome not in weights:
            continue
        total += weights[outcome]
        n += 1
    if n == 0:
        return 0.0
    return round(total / n, 3)


def assess_trust(
    *,
    run_id: str,
    trace_id: str,
    recommendation_id: str,
    confidence: float,
    decision_history: list[dict[str, Any]] | None = None,
    adjudication_bundle: dict[str, Any] | None = None,
    prior_mode: str = "shadow",
) -> dict[str, Any]:
    """Produce a trust record for a single RGE recommendation.

    Args:
        run_id, trace_id: lineage
        recommendation_id: id of the proposal being trusted
        confidence: model confidence [0,1]
        decision_history: list of {"outcome": ...} entries from prior proposals
        adjudication_bundle: dict containing "cde_decision" and "tpa_record"
            required for any mode *transition*
        prior_mode: the prior resolved mode for this surface

    Returns:
        schema-validated rge_trust_record
    """
    if prior_mode not in _MODES:
        prior_mode = "shadow"

    score = _evidence_coverage_score(decision_history or [])
    desired = _mode_for(score)

    bundle = adjudication_bundle or {}
    has_cde = bool(bundle.get("cde_decision"))
    has_tpa = bool(bundle.get("tpa_record"))
    has_both = has_cde and has_tpa

    # Calibration: how close is confidence to historical acceptance rate?
    calibration_gap = round(abs(float(confidence) - score), 3)

    transition_blocked = False
    transition_reason: str | None = None
    if desired == prior_mode:
        resolved_mode = prior_mode
    elif has_both:
        resolved_mode = desired
    else:
        resolved_mode = prior_mode
        transition_blocked = True
        transition_reason = (
            f"Transition {prior_mode} -> {desired} requires both a CDE decision "
            "and a TPA record. Remaining in prior mode."
        )

    execute = resolved_mode != "shadow"

    record = {
        "artifact_type": "rge_trust_record",
        "schema_version": "1.0.0",
        "record_id": _stable_id({
            "run_id": run_id,
            "recommendation_id": recommendation_id,
            "mode": resolved_mode,
        }),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "recommendation_id": recommendation_id,
        "confidence": round(float(confidence), 3),
        "evidence_coverage_score": score,
        "calibration_gap": calibration_gap,
        "prior_mode": prior_mode,
        "desired_mode": desired,
        "resolved_mode": resolved_mode,
        "execute": execute,
        "adjudication_has_cde": has_cde,
        "adjudication_has_tpa": has_tpa,
        "transition_blocked": transition_blocked,
        "transition_reason": transition_reason,
        "thresholds": {
            "shadow_to_warn_gated": SHADOW_TO_WARN_GATED,
            "warn_gated_to_autonomous": WARN_GATED_TO_AUTO,
        },
    }

    validate_artifact(record, "rge_trust_record")
    return record

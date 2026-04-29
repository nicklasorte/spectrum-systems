"""OBS/FRE: failure_explanation — rich debuggability packet for BLOCK/FREEZE outcomes (CLX-ALL-01 Phase 5).

Builds a ``failure_explanation_packet`` that enables triage in under 5 minutes.
Attached to all BLOCK and FREEZE outcomes.

Must include:
  - primary_reason (non-empty)
  - stage_of_failure (from canonical enum: AEX/PQX/EVL/TPA/CDE/SEL/…)
  - triggering_artifact (artifact_type + artifact_id)
  - expected_behavior (what the system expected)
  - actual_behavior (what actually happened)
  - suggested_repair (if safe; None otherwise)

Non-owning: this module interprets evidence and emits advisory packets.
Canonical owners (CDE/SEL/GOV) consume this for triage; it does not
override their decisions.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

# Valid outcome types.
_VALID_OUTCOMES = frozenset(["block", "freeze"])

# Valid stage names.
_VALID_STAGES = frozenset([
    "AEX", "PQX", "EVL", "TPA", "CDE", "SEL",
    "REP", "LIN", "GOV", "FRE", "OBS", "unknown",
])

# Stage-to-owner mapping for repair suggestions.
_STAGE_REPAIR_HINTS: dict[str, str] = {
    "AEX": "Check admission evidence: build_admission_record completeness and authority boundaries.",
    "PQX": "Check execution record: pqx_slice_execution_record coverage and slice authorization.",
    "EVL": "Check eval coverage: required_eval_coverage and evaluation_control_decision.",
    "TPA": "Check trust policy: trust_policy_decision and trust_spine_invariant_result.",
    "CDE": "Check closure decision: closure_decision_artifact and promotion_readiness_decision.",
    "SEL": "Check enforcement: enforcement_action_record and enforcement_block_record.",
    "REP": "Check replay: replay_run_record integrity and replay_integrity_result.",
    "LIN": "Check lineage: artifact_lineage_record and lineage_authenticity_result.",
    "GOV": "Check governance: proof_presence_enforcement_result and certification_evidence_index.",
    "FRE": "Check failure diagnosis: failure_diagnosis_record and repair_plan_artifact.",
    "OBS": "Check observability: observability_metrics_record and trace_store_record.",
    "unknown": "Stage of failure could not be determined. Review trace logs and failure packet.",
}


class FailureExplanationError(ValueError):
    """Raised when the explanation packet cannot be built deterministically."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _packet_id(trace_id: str) -> str:
    digest = hashlib.sha256(f"fep-{trace_id}-{_now()}".encode()).hexdigest()[:12]
    return f"fep-{digest}"


def _infer_stage_from_artifact_type(artifact_type: str) -> str:
    """Infer the most likely stage of failure from the triggering artifact type."""
    low = artifact_type.lower()
    if any(k in low for k in ["admission", "aex", "build_admission"]):
        return "AEX"
    if any(k in low for k in ["pqx", "slice_execution", "bundle_execution"]):
        return "PQX"
    if any(k in low for k in ["eval", "evaluation", "required_eval"]):
        return "EVL"
    if any(k in low for k in ["trust_policy", "tpa", "trust_spine"]):
        return "TPA"
    if any(k in low for k in ["closure_decision", "cde", "promotion_readiness"]):
        return "CDE"
    if any(k in low for k in ["proof_presence"]):
        return "GOV"
    if any(k in low for k in ["enforcement_action", "enforcement_block", "sel_enforcement"]):
        return "SEL"
    if any(k in low for k in ["failure_diagnosis", "repair_plan", "fre"]):
        return "FRE"
    if any(k in low for k in ["replay"]):
        return "REP"
    if any(k in low for k in ["lineage", "lin"]):
        return "LIN"
    if any(k in low for k in ["proof_presence", "governance", "gov", "certification"]):
        return "GOV"
    if any(k in low for k in ["observability", "trace_store", "obs"]):
        return "OBS"
    if any(k in low for k in ["authority_repair"]):
        return "FRE"
    if any(k in low for k in ["authority_preflight"]):
        return "AEX"
    return "unknown"


def build_failure_explanation_packet(
    *,
    trace_id: str,
    outcome: str,
    primary_reason: str,
    triggering_artifact_type: str,
    triggering_artifact_id: str,
    expected_behavior: str,
    actual_behavior: str,
    run_id: str = "",
    stage_of_failure: str | None = None,
    suggested_repair: str | None = None,
    repair_safe: bool | None = None,
    operator_action: str | None = None,
    ambiguity_note: str | None = None,
    triggering_artifact_ref: str | None = None,
) -> dict[str, Any]:
    """Build a ``failure_explanation_packet`` for a BLOCK or FREEZE outcome.

    Raises ``FailureExplanationError`` on invalid inputs.
    """
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise FailureExplanationError("trace_id must be a non-empty string")
    if outcome not in _VALID_OUTCOMES:
        raise FailureExplanationError(f"outcome must be one of {sorted(_VALID_OUTCOMES)}, got '{outcome}'")
    if not primary_reason or not isinstance(primary_reason, str):
        raise FailureExplanationError("primary_reason must be a non-empty string")
    if not triggering_artifact_type:
        raise FailureExplanationError("triggering_artifact_type must be a non-empty string")
    if not triggering_artifact_id:
        raise FailureExplanationError("triggering_artifact_id must be a non-empty string")
    if not expected_behavior:
        raise FailureExplanationError("expected_behavior must be a non-empty string")
    if not actual_behavior:
        raise FailureExplanationError("actual_behavior must be a non-empty string")

    inferred_stage = stage_of_failure or _infer_stage_from_artifact_type(triggering_artifact_type)
    if inferred_stage not in _VALID_STAGES:
        inferred_stage = "unknown"

    # Auto-generate suggested_repair from stage hint if not provided.
    if suggested_repair is None:
        hint = _STAGE_REPAIR_HINTS.get(inferred_stage, _STAGE_REPAIR_HINTS["unknown"])
        suggested_repair = hint
        repair_safe = True

    return {
        "artifact_type": "failure_explanation_packet",
        "schema_version": "1.0.0",
        "packet_id": _packet_id(trace_id),
        "trace_id": trace_id,
        "run_id": run_id,
        "outcome": outcome,
        "primary_reason": primary_reason,
        "stage_of_failure": inferred_stage,
        "triggering_artifact": {
            "artifact_type": triggering_artifact_type,
            "artifact_id": triggering_artifact_id,
            "artifact_ref": triggering_artifact_ref or triggering_artifact_id,
        },
        "expected_behavior": expected_behavior,
        "actual_behavior": actual_behavior,
        "suggested_repair": suggested_repair,
        "repair_safe": repair_safe,
        "operator_action": operator_action,
        "ambiguity_note": ambiguity_note,
        "emitted_at": _now(),
    }


def attach_explanation_to_block_outcome(
    *,
    block_outcome: dict[str, Any],
    trace_id: str,
    run_id: str = "",
) -> dict[str, Any]:
    """Convenience: derive and attach a failure_explanation_packet to a block/freeze outcome dict.

    The outcome dict must have:
      - ``outcome_type``: "block" or "freeze"
      - ``reason_code`` or ``block_reason``: string
      - ``triggering_artifact_type``: string
      - ``triggering_artifact_id``: string
      - ``expected_behavior``: string (optional, defaulted)
      - ``actual_behavior``: string (optional, defaulted)

    Returns the explanation packet.
    """
    if not isinstance(block_outcome, dict):
        raise FailureExplanationError("block_outcome must be a dict")

    outcome_type = str(block_outcome.get("outcome_type") or block_outcome.get("gate_status") or "block")
    if outcome_type not in _VALID_OUTCOMES:
        outcome_type = "block"

    reason = (
        str(block_outcome.get("reason_code") or "")
        or str(block_outcome.get("block_reason") or "")
        or str(block_outcome.get("primary_reason") or "")
        or "unknown_block_reason"
    )

    art_type = str(block_outcome.get("triggering_artifact_type") or block_outcome.get("artifact_type") or "unknown_artifact")
    art_id = str(block_outcome.get("triggering_artifact_id") or block_outcome.get("artifact_id") or "unknown_id")
    expected = str(block_outcome.get("expected_behavior") or "System expected successful completion")
    actual = str(block_outcome.get("actual_behavior") or f"System blocked with reason: {reason}")

    return build_failure_explanation_packet(
        trace_id=trace_id,
        run_id=run_id,
        outcome=outcome_type,
        primary_reason=reason,
        triggering_artifact_type=art_type,
        triggering_artifact_id=art_id,
        expected_behavior=expected,
        actual_behavior=actual,
    )


__all__ = [
    "FailureExplanationError",
    "build_failure_explanation_packet",
    "attach_explanation_to_block_outcome",
]

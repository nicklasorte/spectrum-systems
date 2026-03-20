"""SLO Evaluator (BH–BJ SLO Control Plane).

Maps validator execution results produced by BN.8 validator_engine into
governed Service Level Indicators (SLIs) and derives the overall SLO status.

SLI mapping
-----------
completeness          – fraction of requested validators that passed
timeliness            – pass rate for timeliness-related validators
traceability          – pass rate for traceability-related validators
traceability_integrity – pass/fail of validate_traceability_integrity

SLO classification thresholds
------------------------------
All SLIs >= 0.95          → healthy
Any SLI < 0.85            → breached
Otherwise                 → degraded

Public API
----------
map_validator_results_to_slis(result)  – validator execution result → {sli: float}
compute_slo_status(slis, thresholds)   – slis + thresholds → status dict
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from spectrum_systems.modules.runtime.trace_engine import (
    SPAN_STATUS_BLOCKED,
    SPAN_STATUS_OK,
    SpanNotFoundError,
    TraceNotFoundError,
    end_span,
    record_event,
    start_span,
)

# Default SLO thresholds — these values are governed and intentional.
# >= HEALTHY_THRESHOLD          → healthy
# >= DEGRADED_THRESHOLD and < HEALTHY_THRESHOLD → degraded
# <  DEGRADED_THRESHOLD         → breached
_HEALTHY_THRESHOLD: float = 0.95
_DEGRADED_THRESHOLD: float = 0.85

# Canonical SLI names
_GOVERNED_SLIS: frozenset = frozenset({
    "completeness",
    "timeliness",
    "traceability",
    "traceability_integrity",
})

# Validators that contribute to each SLI bucket
_TIMELINESS_VALIDATORS: frozenset = frozenset({
    "validate_runtime_compatibility",
    "validate_bundle_contract",
})

_TRACEABILITY_VALIDATORS: frozenset = frozenset({
    "validate_artifact_completeness",
    "validate_cross_artifact_consistency",
})

_TRACEABILITY_INTEGRITY_VALIDATOR: str = "validate_traceability_integrity"


def map_validator_results_to_slis(
    result: Dict[str, Any],
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
) -> Dict[str, float]:
    """Map a ValidatorExecutionResult to a governed SLI dict.

    Parameters
    ----------
    result:
        A ``ValidatorExecutionResult`` dict as produced by
        :func:`~spectrum_systems.modules.runtime.validator_engine.run_validators`.
    trace_id:
        Optional trace ID for BK–BM span recording.
    parent_span_id:
        Optional parent span ID for nesting.

    Returns
    -------
    dict
        ``{sli_name: float}`` with exactly the four governed SLIs.
        All values are in ``[0.0, 1.0]``.
        On any error the function returns all SLIs as ``0.0`` (fail-closed).
    """
    sli_span_id: Optional[str] = None
    if trace_id:
        try:
            sli_span_id = start_span(trace_id, "sli_mapping", parent_span_id)
        except (TraceNotFoundError, SpanNotFoundError):
            sli_span_id = None

    try:
        validator_results: List[Dict[str, Any]] = result.get("validator_results") or []
        validators_requested: List[str] = result.get("validators_requested") or []

        # Build lookup: validator_name → status
        status_map: Dict[str, str] = {}
        for vr in validator_results:
            name = vr.get("validator_name", "")
            if name:
                status_map[name] = vr.get("status", "error")

        # --- completeness: fraction of requested validators that passed ---
        if validators_requested:
            passed = sum(
                1 for name in validators_requested
                if status_map.get(name) == "pass"
            )
            completeness = passed / len(validators_requested)
        else:
            completeness = 0.0

        # --- timeliness: pass rate for timeliness-related validators ---
        timeliness_names = [
            n for n in validators_requested if n in _TIMELINESS_VALIDATORS
        ]
        if timeliness_names:
            passed = sum(
                1 for n in timeliness_names if status_map.get(n) == "pass"
            )
            timeliness = passed / len(timeliness_names)
        elif validators_requested:
            # Infer from overall pass rate when no explicit timeliness validators
            timeliness = completeness
        else:
            timeliness = 0.0

        # --- traceability: pass rate for traceability-related validators ---
        traceability_names = [
            n for n in validators_requested if n in _TRACEABILITY_VALIDATORS
        ]
        if traceability_names:
            passed = sum(
                1 for n in traceability_names if status_map.get(n) == "pass"
            )
            traceability = passed / len(traceability_names)
        elif validators_requested:
            traceability = completeness
        else:
            traceability = 0.0

        # --- traceability_integrity: 1.0 if pass, 0.0 otherwise ---
        ti_status = status_map.get(_TRACEABILITY_INTEGRITY_VALIDATOR)
        if ti_status is None:
            # Not requested — infer from overall completeness
            traceability_integrity = completeness
        elif ti_status == "pass":
            traceability_integrity = 1.0
        else:
            traceability_integrity = 0.0

        sli_result = {
            "completeness": round(completeness, 6),
            "timeliness": round(timeliness, 6),
            "traceability": round(traceability, 6),
            "traceability_integrity": round(traceability_integrity, 6),
        }
        if sli_span_id:
            try:
                record_event(sli_span_id, "sli_mapping_complete", sli_result)
                end_span(sli_span_id, SPAN_STATUS_OK)
            except (TraceNotFoundError, SpanNotFoundError):
                pass
        return sli_result

    except Exception:  # noqa: BLE001 — fail closed
        if sli_span_id:
            try:
                end_span(sli_span_id, SPAN_STATUS_BLOCKED)
            except (TraceNotFoundError, SpanNotFoundError):
                pass
        return {
            "completeness": 0.0,
            "timeliness": 0.0,
            "traceability": 0.0,
            "traceability_integrity": 0.0,
        }


def compute_slo_status(
    slis: Dict[str, float],
    thresholds: Optional[Dict[str, float]] = None,
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Derive SLO status from SLI measurements.

    Parameters
    ----------
    slis:
        ``{sli_name: float}`` mapping — must include all four governed SLIs.
    thresholds:
        Optional override for ``healthy`` and ``degraded`` thresholds.
        Keys: ``"healthy"`` (default 0.95), ``"degraded"`` (default 0.85).
    trace_id:
        Optional trace ID for BK–BM span recording.
    parent_span_id:
        Optional parent span ID for nesting.

    Returns
    -------
    dict::

        {
            "slo_status": "healthy" | "degraded" | "breached",
            "violations": [sli_name, ...],
            "scores": {sli_name: float}
        }

    On any error the function returns ``slo_status="breached"`` (fail-closed).
    """
    slo_span_id: Optional[str] = None
    if trace_id:
        try:
            slo_span_id = start_span(trace_id, "slo_computation", parent_span_id)
        except (TraceNotFoundError, SpanNotFoundError):
            slo_span_id = None

    try:
        healthy_t = float((thresholds or {}).get("healthy", _HEALTHY_THRESHOLD))
        degraded_t = float((thresholds or {}).get("degraded", _DEGRADED_THRESHOLD))

        violations: List[str] = []
        for sli_name in sorted(_GOVERNED_SLIS):
            value = slis.get(sli_name, 0.0)
            if value < degraded_t:
                violations.append(sli_name)

        if violations:
            slo_status = "breached"
        elif any(slis.get(s, 0.0) < healthy_t for s in _GOVERNED_SLIS):
            slo_status = "degraded"
        else:
            slo_status = "healthy"

        slo_result = {
            "slo_status": slo_status,
            "violations": violations,
            "scores": dict(slis),
        }
        if slo_span_id:
            try:
                record_event(slo_span_id, "slo_computation_complete", {
                    "slo_status": slo_status,
                    "violations": violations,
                })
                span_st = SPAN_STATUS_OK if slo_status == "healthy" else SPAN_STATUS_BLOCKED
                end_span(slo_span_id, span_st)
            except (TraceNotFoundError, SpanNotFoundError):
                pass
        return slo_result

    except Exception:  # noqa: BLE001 — fail closed
        if slo_span_id:
            try:
                end_span(slo_span_id, SPAN_STATUS_BLOCKED)
            except (TraceNotFoundError, SpanNotFoundError):
                pass
        return {
            "slo_status": "breached",
            "violations": list(_GOVERNED_SLIS),
            "scores": dict(slis) if isinstance(slis, dict) else {},
        }

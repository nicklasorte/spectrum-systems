"""SLO Enforcer (BH–BJ SLO Control Plane).

Translates SLO health status and error budget burn rates into a governed
enforcement decision (allow / warn / block).

Policy
------
- breached                        → block
- degraded + high burn rate       → warn
- degraded + acceptable burn rate → warn  (any degraded state warrants attention)
- healthy                         → allow

Fail-closed: any unexpected error → block.

High burn rate threshold: overall burn_rate > 0.20

Public API
----------
enforce_slo_policy(slo_status, burn_rate) → {"action": str, "reason": str}
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from spectrum_systems.modules.runtime.trace_engine import (
    SPAN_STATUS_BLOCKED,
    SPAN_STATUS_OK,
    SpanNotFoundError,
    TraceNotFoundError,
    end_span,
    record_event,
    start_span,
)

# Enforcement actions
ACTION_ALLOW = "allow"
ACTION_WARN = "warn"
ACTION_BLOCK = "block"

# Threshold above which the overall burn rate is considered "high"
_HIGH_BURN_RATE_THRESHOLD: float = 0.20


def enforce_slo_policy(
    slo_status: str,
    burn_rate: Dict[str, float],
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
) -> Dict[str, str]:
    """Derive an enforcement decision from SLO status and burn rate.

    Parameters
    ----------
    slo_status:
        ``"healthy"``, ``"degraded"``, or ``"breached"``.
    burn_rate:
        Dict produced by :func:`~spectrum_systems.modules.runtime.error_budget.compute_burn_rate`.
        Must include an ``"overall"`` key.
    trace_id:
        Optional trace ID for BK–BM span recording.
    parent_span_id:
        Optional parent span ID for nesting.

    Returns
    -------
    dict::

        {
            "action": "allow" | "warn" | "block",
            "reason": str
        }

    The function is fail-closed: any unexpected input or internal error
    produces ``action="block"``.
    """
    enf_span_id: Optional[str] = None
    if trace_id:
        try:
            enf_span_id = start_span(trace_id, "slo_enforcement_decision", parent_span_id)
        except (TraceNotFoundError, SpanNotFoundError):
            enf_span_id = None

    def _close_span(action: str) -> None:
        if enf_span_id:
            try:
                record_event(enf_span_id, "enforcement_decision", {"action": action, "slo_status": slo_status})
                span_st = SPAN_STATUS_OK if action == ACTION_ALLOW else SPAN_STATUS_BLOCKED
                end_span(enf_span_id, span_st)
            except (TraceNotFoundError, SpanNotFoundError):
                pass

    try:
        if not isinstance(slo_status, str):
            result = {
                "action": ACTION_BLOCK,
                "reason": "enforce_slo_policy: slo_status is not a string; failing closed",
            }
            _close_span(ACTION_BLOCK)
            return result

        if not isinstance(burn_rate, dict):
            result = {
                "action": ACTION_BLOCK,
                "reason": "enforce_slo_policy: burn_rate is not a dict; failing closed",
            }
            _close_span(ACTION_BLOCK)
            return result

        overall_burn = float(burn_rate.get("overall", 0.0))

        if slo_status == "breached":
            result = {
                "action": ACTION_BLOCK,
                "reason": "SLO breached: one or more SLIs are below the minimum threshold",
            }
            _close_span(ACTION_BLOCK)
            return result

        if slo_status == "degraded":
            if overall_burn > _HIGH_BURN_RATE_THRESHOLD:
                result = {
                    "action": ACTION_WARN,
                    "reason": (
                        f"SLO degraded with high burn rate ({overall_burn:.3f} > "
                        f"{_HIGH_BURN_RATE_THRESHOLD}): monitor closely"
                    ),
                }
            else:
                result = {
                    "action": ACTION_WARN,
                    "reason": "SLO degraded: SLIs below healthy threshold, proceeding with warning",
                }
            _close_span(ACTION_WARN)
            return result

        if slo_status == "healthy":
            result = {
                "action": ACTION_ALLOW,
                "reason": "SLO healthy: all SLIs meet thresholds",
            }
            _close_span(ACTION_ALLOW)
            return result

        # Unknown status — fail closed
        result = {
            "action": ACTION_BLOCK,
            "reason": f"enforce_slo_policy: unknown slo_status '{slo_status}'; failing closed",
        }
        _close_span(ACTION_BLOCK)
        return result

    except Exception as exc:  # noqa: BLE001 — fail closed
        if enf_span_id:
            try:
                end_span(enf_span_id, SPAN_STATUS_BLOCKED)
            except (TraceNotFoundError, SpanNotFoundError):
                pass
        return {
            "action": ACTION_BLOCK,
            "reason": f"enforce_slo_policy: unexpected error — {exc}; failing closed",
        }

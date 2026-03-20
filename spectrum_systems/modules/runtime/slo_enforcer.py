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

from typing import Any, Dict

# Enforcement actions
ACTION_ALLOW = "allow"
ACTION_WARN = "warn"
ACTION_BLOCK = "block"

# Threshold above which the overall burn rate is considered "high"
_HIGH_BURN_RATE_THRESHOLD: float = 0.20


def enforce_slo_policy(
    slo_status: str,
    burn_rate: Dict[str, float],
) -> Dict[str, str]:
    """Derive an enforcement decision from SLO status and burn rate.

    Parameters
    ----------
    slo_status:
        ``"healthy"``, ``"degraded"``, or ``"breached"``.
    burn_rate:
        Dict produced by :func:`~spectrum_systems.modules.runtime.error_budget.compute_burn_rate`.
        Must include an ``"overall"`` key.

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
    try:
        if not isinstance(slo_status, str):
            return {
                "action": ACTION_BLOCK,
                "reason": "enforce_slo_policy: slo_status is not a string; failing closed",
            }

        if not isinstance(burn_rate, dict):
            return {
                "action": ACTION_BLOCK,
                "reason": "enforce_slo_policy: burn_rate is not a dict; failing closed",
            }

        overall_burn = float(burn_rate.get("overall", 0.0))

        if slo_status == "breached":
            return {
                "action": ACTION_BLOCK,
                "reason": "SLO breached: one or more SLIs are below the minimum threshold",
            }

        if slo_status == "degraded":
            if overall_burn > _HIGH_BURN_RATE_THRESHOLD:
                return {
                    "action": ACTION_WARN,
                    "reason": (
                        f"SLO degraded with high burn rate ({overall_burn:.3f} > "
                        f"{_HIGH_BURN_RATE_THRESHOLD}): monitor closely"
                    ),
                }
            return {
                "action": ACTION_WARN,
                "reason": "SLO degraded: SLIs below healthy threshold, proceeding with warning",
            }

        if slo_status == "healthy":
            return {
                "action": ACTION_ALLOW,
                "reason": "SLO healthy: all SLIs meet thresholds",
            }

        # Unknown status — fail closed
        return {
            "action": ACTION_BLOCK,
            "reason": f"enforce_slo_policy: unknown slo_status '{slo_status}'; failing closed",
        }

    except Exception as exc:  # noqa: BLE001 — fail closed
        return {
            "action": ACTION_BLOCK,
            "reason": f"enforce_slo_policy: unexpected error — {exc}; failing closed",
        }

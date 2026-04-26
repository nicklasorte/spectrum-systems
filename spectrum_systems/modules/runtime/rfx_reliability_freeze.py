"""RFX reliability-freeze guard — LOOP-07.

Part 2 of the RFX reliability/SLO enforcement layer. Reliability is not
advisory: when burst failures, replay drift, recurring failure patterns,
SLO burn, instability, or unknown reliability state are detected, the
guard MUST stop or freeze progression.

This guard is a non-owning phase-label support helper. Canonical authority
for OBS, SLO, REP, and SEL is recorded in
``docs/architecture/system_registry.md``; LOOP-07 interprets evidence and
emits freeze propagation through
:mod:`spectrum_systems.modules.runtime.rfx_freeze_propagation`.

Failure conditions (each fail-closed):
  * ``rfx_burst_failure_detected``        — failure density spike in window
  * ``rfx_recurring_failure_pattern_detected`` — same reason_code repeats
  * ``rfx_failure_trend_increasing``      — failure rate slope positive
  * ``rfx_replay_drift_detected``         — replay mismatch ≥ threshold
  * ``rfx_instability_detected``          — composite score ≥ threshold
  * ``rfx_slo_burn_detected``             — SLO posture / burn unsafe
  * ``rfx_reliability_state_unknown``     — reliability evidence missing

All failures are aggregated and re-raised as one combined error, paired
with a freeze propagation record so downstream guards (PQX/CDE/GOV/SEL)
can see the freeze effect deterministically.
"""

from __future__ import annotations

from typing import Any

from spectrum_systems.modules.runtime.rfx_failure_profile import (
    RFXFailureProfileThresholds,
    build_rfx_failure_profile,
)
from spectrum_systems.modules.runtime.rfx_freeze_propagation import (
    propagate_rfx_freeze,
)


class RFXReliabilityFreezeError(ValueError):
    """Raised when the LOOP-07 reliability-freeze guard fails closed."""

    def __init__(self, message: str, *, freeze_record: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.freeze_record = freeze_record


_SLO_PASSING = frozenset({"pass", "ok", "within_budget", "acceptable"})
_SLO_BURN_FLAGS = ("burn_rate_breach", "burning", "over_budget", "exhausted")


def _is_dict(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _slo_unsafe(slo: dict[str, Any] | None) -> tuple[bool, str | None]:
    """Return (unsafe, reason). Missing SLO is *unknown*, not safe."""
    if not _is_dict(slo):
        return True, "rfx_reliability_state_unknown: SLO posture record absent"

    status = None
    for key in ("status", "posture", "rollout_state"):
        v = slo.get(key)
        if isinstance(v, str) and v.strip():
            status = v.strip()
            break

    if status is None:
        return True, "rfx_reliability_state_unknown: SLO record missing status/posture"

    if status in _SLO_PASSING:
        # Cross-check explicit burn flags even when the headline status looks ok.
        for flag in _SLO_BURN_FLAGS:
            if bool(slo.get(flag)):
                return True, f"rfx_slo_burn_detected: SLO flag {flag!r} set despite status={status!r}"
        return False, None

    return True, f"rfx_slo_burn_detected: SLO status={status!r} not in {sorted(_SLO_PASSING)!r}"


def assert_rfx_reliability_posture(
    *,
    recent_failures: list[dict[str, Any]] | None,
    replay_results: list[dict[str, Any]] | None,
    window_seconds: int,
    slo: dict[str, Any] | None,
    thresholds: RFXFailureProfileThresholds | None = None,
) -> dict[str, Any]:
    """LOOP-07 reliability-freeze guard.

    Returns the failure profile when posture is safe. When unsafe, raises
    :class:`RFXReliabilityFreezeError` carrying the aggregated reason codes
    and a freeze propagation record.
    """
    th = thresholds or RFXFailureProfileThresholds()

    if not isinstance(window_seconds, int) or window_seconds <= 0:
        raise RFXReliabilityFreezeError(
            "rfx_reliability_state_unknown: window_seconds must be a positive integer",
            freeze_record=propagate_rfx_freeze(
                reason_codes=["rfx_reliability_state_unknown"],
                downstream_targets=[],
            ),
        )

    profile = build_rfx_failure_profile(
        recent_failures=recent_failures,
        replay_results=replay_results,
        window_seconds=window_seconds,
        thresholds=th,
    )

    reasons: list[str] = []

    malformed_failures = profile.get("malformed_failure_count", 0)
    malformed_replays = profile.get("malformed_replay_count", 0)
    if malformed_failures or malformed_replays:
        reasons.append(
            f"rfx_malformed_telemetry_input: malformed_failure_count="
            f"{malformed_failures}, malformed_replay_count={malformed_replays} — "
            f"telemetry rows must be mappings; non-dict rows fail closed"
        )

    if profile["burst_failure_detected"]:
        reasons.append(
            "rfx_burst_failure_detected: failure density spike inside window — "
            "reliability freeze required"
        )

    if profile["recurring_failure_pattern"]:
        reasons.append(
            "rfx_recurring_failure_pattern_detected: same reason_code observed "
            "repeatedly — reliability freeze required"
        )

    if profile["failure_trend_increasing"]:
        reasons.append(
            "rfx_failure_trend_increasing: failure-rate slope positive over window — "
            "reliability freeze required"
        )

    if profile["replay_mismatch_rate"] >= th.replay_mismatch_rate_block:
        reasons.append(
            f"rfx_replay_drift_detected: replay mismatch rate "
            f"{profile['replay_mismatch_rate']:.4f} ≥ {th.replay_mismatch_rate_block:.4f}"
        )

    if profile["instability_score"] >= th.instability_score_block:
        reasons.append(
            f"rfx_instability_detected: composite instability score "
            f"{profile['instability_score']:.4f} ≥ {th.instability_score_block:.4f}"
        )

    slo_bad, slo_reason = _slo_unsafe(slo)
    if slo_bad and slo_reason is not None:
        reasons.append(slo_reason)

    if reasons:
        record = propagate_rfx_freeze(
            reason_codes=reasons,
            downstream_targets=[],
        )
        raise RFXReliabilityFreezeError(
            "; ".join(reasons),
            freeze_record=record,
        )

    return profile


__all__ = [
    "RFXReliabilityFreezeError",
    "assert_rfx_reliability_posture",
]

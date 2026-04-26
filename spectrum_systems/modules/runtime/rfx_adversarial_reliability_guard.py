"""RFX adversarial reliability guard — Part 6 anti-gaming defense.

Detects attempts to game the LOOP-07/LOOP-08 reliability gates by
suppressing failure signals, fabricating consistency, or hiding entire
slices of data. The guard is fail-closed and produces deterministic
reason codes.

Detection vectors:

  * Artificially suppressed failure signals
      e.g. ``recent_failures = []`` while OBS ``failure_logs`` are non-empty
      or the SLO record shows burn flags.
  * Inconsistent metrics
      e.g. ``failure_count == 0`` while ``replay_results`` show mismatches,
      or ``replay_mismatch_rate > 0`` while no failure was recorded.
  * Missing slices of data
      e.g. OBS missing required slices (failure_logs / artifact_linkage /
      execution_path_coverage) while SLO posture is ``ok``, indicating an
      attempt to claim healthy posture without supporting telemetry.

Reason codes:

  * ``rfx_metrics_inconsistency``
  * ``rfx_suspicious_signal_suppression``
  * ``rfx_missing_data_slice``

This guard is a non-owning phase-label support helper. Canonical authority
for OBS, SLO, and REP is recorded in
``docs/architecture/system_registry.md``.
"""

from __future__ import annotations

from typing import Any


class RFXAdversarialReliabilityError(ValueError):
    """Raised when adversarial reliability inconsistency is detected."""


_OBS_REQUIRED_SLICES: tuple[str, ...] = (
    "execution_path_coverage",
    "artifact_linkage",
    "failure_logs",
)

_SLO_OK = frozenset({"pass", "ok", "within_budget", "acceptable"})
_SLO_BURN_FLAGS = ("burn_rate_breach", "burning", "over_budget", "exhausted")


def _is_dict(value: Any) -> bool:
    return isinstance(value, dict)


def _replay_mismatch_count(replay_results: list[dict[str, Any]] | None) -> int:
    if not replay_results:
        return 0
    mismatches = 0
    for r in replay_results:
        if not isinstance(r, dict):
            continue
        flag = None
        for key in ("match", "replay_match", "matches"):
            if key in r and isinstance(r[key], bool):
                flag = r[key]
                break
        if flag is False:
            mismatches += 1
    return mismatches


def _obs_failure_log_count(obs: dict[str, Any]) -> int:
    logs = obs.get("failure_logs")
    if isinstance(logs, list):
        return len(logs)
    return 0


def _slo_status(slo: dict[str, Any]) -> str | None:
    for key in ("status", "posture", "rollout_state"):
        v = slo.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def assert_rfx_adversarial_reliability_guard(
    *,
    recent_failures: list[dict[str, Any]] | None,
    replay_results: list[dict[str, Any]] | None,
    obs: dict[str, Any] | None,
    slo: dict[str, Any] | None,
) -> None:
    """Detect anti-gaming inconsistencies; fail closed deterministically."""
    reasons: list[str] = []

    failures = list(recent_failures or [])
    replays = list(replay_results or [])
    obs_present = _is_dict(obs) and bool(obs)
    slo_present = _is_dict(slo) and bool(slo)

    failure_count = len(failures)
    replay_mismatches = _replay_mismatch_count(replays)
    obs_failure_logs = _obs_failure_log_count(obs) if obs_present else 0
    slo_status = _slo_status(slo) if slo_present else None
    slo_burn = bool(slo_present and any(slo.get(f) for f in _SLO_BURN_FLAGS))

    # ---- Suppressed failure signals -----------------------------------
    if failure_count == 0 and obs_failure_logs > 0:
        reasons.append(
            f"rfx_suspicious_signal_suppression: recent_failures empty but "
            f"OBS failure_logs has {obs_failure_logs} entries"
        )
    if failure_count == 0 and slo_burn:
        reasons.append(
            "rfx_suspicious_signal_suppression: recent_failures empty but "
            "SLO record carries explicit burn flags"
        )

    # ---- Metrics inconsistency ---------------------------------------
    if failure_count == 0 and replay_mismatches > 0:
        reasons.append(
            f"rfx_metrics_inconsistency: 0 failures recorded but "
            f"{replay_mismatches} replay mismatches present"
        )
    if (
        slo_present
        and slo_status in _SLO_OK
        and (replay_mismatches > 0 or obs_failure_logs > 0)
    ):
        reasons.append(
            "rfx_metrics_inconsistency: SLO status="
            f"{slo_status!r} ok-band while replay/OBS show "
            f"failures (replay_mismatches={replay_mismatches}, "
            f"obs_failure_logs={obs_failure_logs})"
        )

    # ---- Missing slices ----------------------------------------------
    if obs_present:
        missing_slices = [k for k in _OBS_REQUIRED_SLICES if obs.get(k) is None]
        if missing_slices and slo_status in _SLO_OK:
            reasons.append(
                "rfx_missing_data_slice: SLO claims ok while OBS is missing "
                "slices: " + ", ".join(sorted(missing_slices))
            )
    else:
        if slo_present and slo_status in _SLO_OK:
            reasons.append(
                "rfx_missing_data_slice: SLO claims ok with no OBS record at all"
            )

    if reasons:
        raise RFXAdversarialReliabilityError("; ".join(reasons))


__all__ = [
    "RFXAdversarialReliabilityError",
    "assert_rfx_adversarial_reliability_guard",
]

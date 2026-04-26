"""RFX failure profile model — telemetry-derived reliability snapshot.

Builds a deterministic ``rfx_failure_profile`` summary from a window of
recent failures and replay results. The profile is consumed by:

  * LOOP-07 — :func:`assert_rfx_reliability_posture` (reliability-freeze guard)
  * LOOP-08 — :func:`assert_rfx_telemetry_slo_eligible` (SLO eligibility)
  * Adversarial reliability guard
  * The ``rfx_reliability_trend_record`` emitter (Part 9 light-version trend
    memory consumed by RFX-05).

This module is a non-owning phase-label support helper. Canonical roles for
OBS, SLO, REP, and SEL are recorded in
``docs/architecture/system_registry.md``; the failure profile interprets
upstream evidence and does not redefine ownership.

Thresholds are conservative defaults. Callers can override them through
:class:`RFXFailureProfileThresholds` for governed-policy tuning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class RFXFailureProfileThresholds:
    """Deterministic thresholds for failure-profile derivation.

    Defaults are deliberately conservative — fail-closed on weak signals.
    """

    # Density spike: a "burst" is declared when at least this fraction of
    # the window's failures fall inside the most recent ``burst_window_frac``
    # of the window.
    burst_failure_density: float = 0.5
    burst_window_frac: float = 0.25
    burst_min_failures: int = 3

    # Same reason_code seen at least this many times → recurring pattern.
    recurring_min_repeats: int = 2

    # Trend slope: failure rate later in the window vs. earlier; positive
    # ratio above this threshold marks an increasing trend.
    trend_slope_increase_ratio: float = 1.25
    trend_min_failures: int = 3

    # Replay mismatch above this fraction is treated as drift.
    replay_mismatch_rate_block: float = 0.10

    # Instability score weights (sum ≤ 1.0; the score is bounded to [0, 1]).
    weight_failure_rate: float = 0.4
    weight_replay_mismatch: float = 0.4
    weight_trend_slope: float = 0.2

    # Instability score above this is considered unsafe.
    instability_score_block: float = 0.5


_DEFAULT_THRESHOLDS = RFXFailureProfileThresholds()


def _coerce_timestamp(record: dict[str, Any]) -> float | None:
    """Return a numeric timestamp (seconds) for a record, or ``None``.

    Accepts ``timestamp_seconds`` / ``ts`` / ``elapsed_seconds`` /
    ``occurred_at_seconds`` / ``occurred_at`` when the value is numeric,
    interpreted as monotonic seconds since the window start. Non-numeric
    values (including ISO date-time strings) are ignored deliberately —
    failure profiling must not infer timing from free-form string parsing.
    """
    for key in ("timestamp_seconds", "ts", "elapsed_seconds", "occurred_at_seconds", "occurred_at"):
        if key in record and isinstance(record[key], (int, float)) and not isinstance(record[key], bool):
            return float(record[key])
    return None


def _coerce_reason_code(record: dict[str, Any]) -> str | None:
    for key in ("reason_code", "code", "failure_code", "classification"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _coerce_match_flag(record: dict[str, Any]) -> bool | None:
    for key in ("match", "replay_match", "matches"):
        if key in record:
            value = record[key]
            if isinstance(value, bool):
                return value
    return None


def _failure_rate(failure_count: int, window_seconds: int) -> float:
    if window_seconds <= 0:
        return 0.0
    return failure_count / float(window_seconds)


def _detect_burst(
    failures: list[dict[str, Any]],
    window_seconds: int,
    thresholds: RFXFailureProfileThresholds,
) -> bool:
    """Return True if failure density is concentrated in the recent tail.

    Uses numeric ``timestamp_seconds`` (or aliases) measured from the start
    of the window. Records without numeric timestamps are conservatively
    counted toward the recent tail only if every record is missing one,
    which still lets an all-recent burst register.
    """
    if window_seconds <= 0 or len(failures) < thresholds.burst_min_failures:
        return False

    cutoff = window_seconds * (1.0 - thresholds.burst_window_frac)
    timed = [_coerce_timestamp(f) for f in failures]
    if all(t is None for t in timed):
        # No timing signal — cannot detect burst structure deterministically.
        return False

    recent = sum(1 for t in timed if t is not None and t >= cutoff)
    total = sum(1 for t in timed if t is not None)
    if total == 0:
        return False

    density = recent / float(total)
    return density >= thresholds.burst_failure_density


def _detect_recurring(
    failures: Iterable[dict[str, Any]],
    thresholds: RFXFailureProfileThresholds,
) -> bool:
    counts: dict[str, int] = {}
    for f in failures:
        code = _coerce_reason_code(f)
        if code is None:
            continue
        counts[code] = counts.get(code, 0) + 1
    return any(c >= thresholds.recurring_min_repeats for c in counts.values())


def _trend_slope_increasing(
    failures: list[dict[str, Any]],
    window_seconds: int,
    thresholds: RFXFailureProfileThresholds,
) -> bool:
    """Compare failure count in second half vs. first half of the window."""
    if window_seconds <= 0 or len(failures) < thresholds.trend_min_failures:
        return False
    midpoint = window_seconds / 2.0
    earlier = 0
    later = 0
    timed = 0
    for f in failures:
        t = _coerce_timestamp(f)
        if t is None:
            continue
        timed += 1
        if t < midpoint:
            earlier += 1
        else:
            later += 1
    if timed == 0:
        return False
    if earlier == 0:
        # All failures in the second half → increasing.
        return later >= thresholds.trend_min_failures
    return (later / float(earlier)) >= thresholds.trend_slope_increase_ratio


def _replay_mismatch_rate(replay_results: list[dict[str, Any]]) -> float:
    if not replay_results:
        return 0.0
    matches = 0
    counted = 0
    for r in replay_results:
        flag = _coerce_match_flag(r)
        if flag is None:
            # A replay result without a deterministic match signal is itself
            # a drift indicator — count it as a mismatch so suppression of
            # the field cannot mask drift.
            counted += 1
            continue
        counted += 1
        if flag:
            matches += 1
    if counted == 0:
        return 0.0
    return 1.0 - (matches / float(counted))


def _instability_score(
    failure_rate: float,
    replay_mismatch_rate: float,
    trend_increasing: bool,
    thresholds: RFXFailureProfileThresholds,
) -> float:
    """Combine signals into a bounded [0, 1] instability score.

    Failure rate is normalized against a saturation point of 1 failure per
    second (any rate at or above that saturates the failure-rate term).
    """
    fr_term = min(failure_rate, 1.0) * thresholds.weight_failure_rate
    rm_term = min(max(replay_mismatch_rate, 0.0), 1.0) * thresholds.weight_replay_mismatch
    ts_term = (1.0 if trend_increasing else 0.0) * thresholds.weight_trend_slope
    score = fr_term + rm_term + ts_term
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def build_rfx_failure_profile(
    *,
    recent_failures: list[dict[str, Any]] | None,
    replay_results: list[dict[str, Any]] | None,
    window_seconds: int,
    thresholds: RFXFailureProfileThresholds | None = None,
) -> dict[str, Any]:
    """Build a deterministic failure profile over the supplied window.

    The profile is fail-closed on missing inputs: ``None`` is treated as an
    empty list, and a non-positive window collapses derived rates to zero
    while preserving the raw counts so downstream guards still see the
    structural signal.

    Malformed rows (anything that is not a ``dict``) are filtered out
    before profiling so downstream helpers cannot raise raw
    ``AttributeError``/``TypeError`` from the promotion path. The counts of
    filtered rows are surfaced as ``malformed_failure_count`` /
    ``malformed_replay_count`` so the LOOP-07 reliability-freeze guard can
    convert them into a deterministic ``rfx_malformed_telemetry_input``
    reason code rather than silently dropping the input.
    """
    th = thresholds or _DEFAULT_THRESHOLDS

    raw_failures = list(recent_failures or [])
    raw_replays = list(replay_results or [])
    failures = [f for f in raw_failures if isinstance(f, dict)]
    replays = [r for r in raw_replays if isinstance(r, dict)]
    malformed_failure_count = len(raw_failures) - len(failures)
    malformed_replay_count = len(raw_replays) - len(replays)

    failure_count = len(failures)
    failure_rate = _failure_rate(failure_count, window_seconds)
    burst = _detect_burst(failures, window_seconds, th)
    recurring = _detect_recurring(failures, th)
    trend_increasing = _trend_slope_increasing(failures, window_seconds, th)
    replay_mismatch_rate = _replay_mismatch_rate(replays)
    score = _instability_score(failure_rate, replay_mismatch_rate, trend_increasing, th)

    return {
        "artifact_type": "rfx_failure_profile",
        "schema_version": "1.0.0",
        "window_seconds": int(window_seconds),
        "failure_count": failure_count,
        "failure_rate": failure_rate,
        "burst_failure_detected": burst,
        "recurring_failure_pattern": recurring,
        "replay_mismatch_rate": replay_mismatch_rate,
        "failure_trend_increasing": trend_increasing,
        "instability_score": score,
        "malformed_failure_count": malformed_failure_count,
        "malformed_replay_count": malformed_replay_count,
        "thresholds": {
            "burst_failure_density": th.burst_failure_density,
            "burst_window_frac": th.burst_window_frac,
            "burst_min_failures": th.burst_min_failures,
            "recurring_min_repeats": th.recurring_min_repeats,
            "trend_slope_increase_ratio": th.trend_slope_increase_ratio,
            "trend_min_failures": th.trend_min_failures,
            "replay_mismatch_rate_block": th.replay_mismatch_rate_block,
            "instability_score_block": th.instability_score_block,
        },
    }


# ---------------------------------------------------------------------------
# Part 9 — light-version trend memory: rfx_reliability_trend_record
# ---------------------------------------------------------------------------


@dataclass
class _TrendSample:
    failure_count: int
    instability_score: float
    replay_mismatch_rate: float
    burst_failure_detected: bool
    recurring_failure_pattern: bool
    failure_trend_increasing: bool


def build_rfx_reliability_trend_record(
    *,
    profile_history: list[dict[str, Any]],
    trace_id: str,
    created_at: str,
) -> dict[str, Any]:
    """Emit a ``rfx_reliability_trend_record`` from an ordered profile history.

    Each entry in ``profile_history`` must be a profile dict produced by
    :func:`build_rfx_failure_profile`. The record carries the failure
    pattern, instability-score history, and replay-drift trend used by
    later RFX-05 trend analysis.
    """
    samples: list[_TrendSample] = []
    for p in profile_history or []:
        if not isinstance(p, dict):
            continue
        samples.append(
            _TrendSample(
                failure_count=int(p.get("failure_count", 0) or 0),
                instability_score=float(p.get("instability_score", 0.0) or 0.0),
                replay_mismatch_rate=float(p.get("replay_mismatch_rate", 0.0) or 0.0),
                burst_failure_detected=bool(p.get("burst_failure_detected", False)),
                recurring_failure_pattern=bool(p.get("recurring_failure_pattern", False)),
                failure_trend_increasing=bool(p.get("failure_trend_increasing", False)),
            )
        )

    return {
        "artifact_type": "rfx_reliability_trend_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "created_at": created_at,
        "sample_count": len(samples),
        "failure_patterns": {
            "burst_count": sum(1 for s in samples if s.burst_failure_detected),
            "recurring_count": sum(1 for s in samples if s.recurring_failure_pattern),
            "trend_increasing_count": sum(1 for s in samples if s.failure_trend_increasing),
        },
        "instability_score_history": [s.instability_score for s in samples],
        "replay_drift_trend": [s.replay_mismatch_rate for s in samples],
        "failure_count_history": [s.failure_count for s in samples],
    }


__all__ = [
    "RFXFailureProfileThresholds",
    "build_rfx_failure_profile",
    "build_rfx_reliability_trend_record",
]

"""Tests for the RFX failure profile model (Part 1) and the
``rfx_reliability_trend_record`` emitter (Part 9)."""

from __future__ import annotations

from spectrum_systems.modules.runtime.rfx_failure_profile import (
    RFXFailureProfileThresholds,
    build_rfx_failure_profile,
    build_rfx_reliability_trend_record,
)


def _failure(ts: float, code: str = "exec_error") -> dict:
    return {"timestamp_seconds": ts, "reason_code": code}


def test_empty_inputs_produce_safe_profile() -> None:
    p = build_rfx_failure_profile(
        recent_failures=[], replay_results=[], window_seconds=60,
    )
    assert p["failure_count"] == 0
    assert p["failure_rate"] == 0.0
    assert p["burst_failure_detected"] is False
    assert p["recurring_failure_pattern"] is False
    assert p["failure_trend_increasing"] is False
    assert p["replay_mismatch_rate"] == 0.0
    assert p["instability_score"] == 0.0


def test_burst_detected_when_density_concentrated_in_tail() -> None:
    # 6 failures, 5 in the last 25% of a 100s window
    failures = [_failure(5.0)] + [_failure(80.0 + i) for i in range(5)]
    p = build_rfx_failure_profile(
        recent_failures=failures, replay_results=[], window_seconds=100,
    )
    assert p["burst_failure_detected"] is True


def test_burst_detected_when_occurred_at_numeric_alias_used() -> None:
    """Producers using the documented ``occurred_at`` numeric alias must
    drive burst/trend detection identically to ``timestamp_seconds``."""
    failures = (
        [{"occurred_at": 5.0, "reason_code": "x"}]
        + [{"occurred_at": 80.0 + i, "reason_code": f"x{i}"} for i in range(5)]
    )
    p = build_rfx_failure_profile(
        recent_failures=failures, replay_results=[], window_seconds=100,
    )
    assert p["burst_failure_detected"] is True


def test_iso_string_occurred_at_treated_as_no_timing_signal() -> None:
    """Non-numeric ``occurred_at`` (ISO datetime string) must be ignored —
    failure profiling never parses free-form timestamp strings."""
    failures = [
        {"occurred_at": "2026-04-25T00:00:05Z", "reason_code": "x"},
        {"occurred_at": "2026-04-25T00:01:25Z", "reason_code": "x"},
    ]
    p = build_rfx_failure_profile(
        recent_failures=failures, replay_results=[], window_seconds=100,
    )
    # Without numeric timing, burst/trend cannot be detected.
    assert p["burst_failure_detected"] is False
    assert p["failure_trend_increasing"] is False


def test_burst_not_detected_when_evenly_distributed() -> None:
    failures = [_failure(t) for t in (5.0, 25.0, 50.0, 75.0, 95.0)]
    p = build_rfx_failure_profile(
        recent_failures=failures, replay_results=[], window_seconds=100,
    )
    assert p["burst_failure_detected"] is False


def test_recurring_failure_pattern_detected() -> None:
    failures = [_failure(t, "schema_drift") for t in (1.0, 10.0, 25.0)]
    p = build_rfx_failure_profile(
        recent_failures=failures, replay_results=[], window_seconds=60,
    )
    assert p["recurring_failure_pattern"] is True


def test_recurring_failure_pattern_distinct_codes_safe() -> None:
    failures = [
        _failure(1.0, "schema_drift"),
        _failure(10.0, "exec_error"),
        _failure(20.0, "policy_block"),
    ]
    p = build_rfx_failure_profile(
        recent_failures=failures, replay_results=[], window_seconds=60,
    )
    assert p["recurring_failure_pattern"] is False


def test_failure_trend_increasing_detected() -> None:
    failures = [_failure(5.0)] + [_failure(60.0 + i * 2) for i in range(5)]
    p = build_rfx_failure_profile(
        recent_failures=failures, replay_results=[], window_seconds=100,
    )
    assert p["failure_trend_increasing"] is True


def test_replay_mismatch_rate_computed() -> None:
    replays = [
        {"trace_id": "t1", "match": True},
        {"trace_id": "t2", "match": False},
        {"trace_id": "t3", "match": False},
        {"trace_id": "t4", "match": True},
    ]
    p = build_rfx_failure_profile(
        recent_failures=[], replay_results=replays, window_seconds=60,
    )
    assert p["replay_mismatch_rate"] == 0.5


def test_replay_missing_match_flag_counts_as_drift() -> None:
    """A replay record stripped of its match flag is itself a drift signal."""
    replays = [{"trace_id": "t1"}, {"trace_id": "t2", "match": True}]
    p = build_rfx_failure_profile(
        recent_failures=[], replay_results=replays, window_seconds=60,
    )
    assert p["replay_mismatch_rate"] == 0.5


def test_instability_score_bounded_unit_interval() -> None:
    failures = [_failure(80.0 + i) for i in range(5)]
    replays = [{"trace_id": f"t{i}", "match": False} for i in range(10)]
    p = build_rfx_failure_profile(
        recent_failures=failures, replay_results=replays, window_seconds=10,
    )
    assert 0.0 <= p["instability_score"] <= 1.0
    assert p["instability_score"] > 0.5  # high signal


def test_thresholds_override() -> None:
    """Custom thresholds must shift detection behavior deterministically."""
    failures = [_failure(t, "code_a") for t in (10.0, 20.0)]
    # Default recurring_min_repeats = 2 → recurring True; override to 5 → False.
    th = RFXFailureProfileThresholds(recurring_min_repeats=5)
    p = build_rfx_failure_profile(
        recent_failures=failures, replay_results=[], window_seconds=60, thresholds=th,
    )
    assert p["recurring_failure_pattern"] is False


def test_zero_window_collapses_rate_keeps_count() -> None:
    failures = [_failure(0.0)] * 3
    p = build_rfx_failure_profile(
        recent_failures=failures, replay_results=[], window_seconds=0,
    )
    assert p["failure_count"] == 3
    assert p["failure_rate"] == 0.0
    assert p["burst_failure_detected"] is False


# ---------------------------------------------------------------------------
# rfx_reliability_trend_record (Part 9)
# ---------------------------------------------------------------------------


def test_trend_record_aggregates_history() -> None:
    p1 = build_rfx_failure_profile(
        recent_failures=[_failure(t) for t in (5.0, 95.0)],
        replay_results=[{"trace_id": "t", "match": False}],
        window_seconds=100,
    )
    p2 = build_rfx_failure_profile(
        recent_failures=[_failure(t, "code_a") for t in (10.0, 20.0)],
        replay_results=[{"trace_id": "t", "match": True}],
        window_seconds=100,
    )
    rec = build_rfx_reliability_trend_record(
        profile_history=[p1, p2],
        trace_id="trace-trend-001",
        created_at="2026-04-25T00:00:00Z",
    )
    assert rec["artifact_type"] == "rfx_reliability_trend_record"
    assert rec["sample_count"] == 2
    assert len(rec["instability_score_history"]) == 2
    assert len(rec["replay_drift_trend"]) == 2
    assert rec["failure_patterns"]["recurring_count"] >= 1


def test_trend_record_empty_history_safe() -> None:
    rec = build_rfx_reliability_trend_record(
        profile_history=[],
        trace_id="t",
        created_at="2026-04-25T00:00:00Z",
    )
    assert rec["sample_count"] == 0
    assert rec["instability_score_history"] == []

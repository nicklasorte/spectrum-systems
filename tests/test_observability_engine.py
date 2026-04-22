"""Tests for Phase 4.1: ObservabilityEngine."""

import pytest

from spectrum_systems.observability.observability_engine import (
    REQUIRED_EXECUTION_EVENTS,
    ObservabilityEngine,
)


@pytest.fixture()
def engine():
    e = ObservabilityEngine()
    yield e
    e.clear()


def _emit_full_trace(engine: ObservabilityEngine, trace_id: str) -> None:
    for evt in REQUIRED_EXECUTION_EVENTS:
        engine.emit_event(trace_id, evt, {"status": "ok"})


# ---------------------------------------------------------------------------
# test_all_events_emitted
# ---------------------------------------------------------------------------
def test_all_events_emitted(engine):
    _emit_full_trace(engine, "trace-1")
    timeline = engine.get_execution_timeline("trace-1")
    event_types = {e["event_type"] for e in timeline}
    assert REQUIRED_EXECUTION_EVENTS.issubset(event_types)


# ---------------------------------------------------------------------------
# test_100_percent_coverage
# ---------------------------------------------------------------------------
def test_100_percent_coverage(engine):
    trace_ids = [f"trace-{i}" for i in range(10)]
    for tid in trace_ids:
        _emit_full_trace(engine, tid)
    rate = engine.coverage_rate(trace_ids)
    assert rate == 1.0


# ---------------------------------------------------------------------------
# test_timeline_ordered
# ---------------------------------------------------------------------------
def test_timeline_ordered(engine):
    for i in range(5):
        engine.emit_event("trace-ord", f"event-{i}", {"seq": i})
    timeline = engine.get_execution_timeline("trace-ord")
    seqs = [e["data"]["seq"] for e in timeline]
    assert seqs == sorted(seqs)


# ---------------------------------------------------------------------------
# test_missing_events_detected
# ---------------------------------------------------------------------------
def test_missing_events_detected(engine):
    # Emit only a subset of required events
    engine.emit_event("trace-partial", "execution_start", {})
    ok, report = engine.validate_completeness("trace-partial")
    assert ok is False
    assert "missing_events" in report
    assert len(report["missing_events"]) > 0


# ---------------------------------------------------------------------------
# test_metrics_dashboard (coverage_rate for mixed traces)
# ---------------------------------------------------------------------------
def test_metrics_dashboard(engine):
    # 8 complete, 2 partial
    complete_ids = [f"c-{i}" for i in range(8)]
    partial_ids = [f"p-{i}" for i in range(2)]

    for tid in complete_ids:
        _emit_full_trace(engine, tid)
    for tid in partial_ids:
        engine.emit_event(tid, "execution_start", {})

    rate = engine.coverage_rate(complete_ids + partial_ids)
    assert rate == 0.8

"""Unit tests for ExecutionEventLog — Phase 2.4 (7 tests + RT-2.4 coverage)."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spectrum_systems.observability.execution_event_log import ExecutionEventLog


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def log():
    return ExecutionEventLog()


# ---------------------------------------------------------------------------
# Test 1: log_event returns event with required fields
# ---------------------------------------------------------------------------


def test_log_event_returns_event_with_required_fields(log):
    event = log.log_event("TRC-001", "execution_start", {"step": "init"})
    assert "event_id" in event
    assert event["event_id"].startswith("EVT-")
    assert event["trace_id"] == "TRC-001"
    assert event["event_type"] == "execution_start"
    assert "timestamp" in event
    assert "seq" in event


# ---------------------------------------------------------------------------
# Test 2: Events are immutable after creation
# ---------------------------------------------------------------------------


def test_events_are_immutable(log):
    event = log.log_event("TRC-002", "admission_gate", {})
    with pytest.raises(TypeError):
        event["event_id"] = "hacked"


# ---------------------------------------------------------------------------
# Test 3: get_execution_timeline returns events in order for trace
# ---------------------------------------------------------------------------


def test_timeline_returns_events_in_order(log):
    log.log_event("TRC-A", "execution_start", {})
    log.log_event("TRC-A", "eval_start", {})
    log.log_event("TRC-A", "eval_end", {})
    timeline = log.get_execution_timeline("TRC-A")
    assert len(timeline) == 3
    seqs = [e["seq"] for e in timeline]
    assert seqs == sorted(seqs), "Events not in sequence order"
    types = [e["event_type"] for e in timeline]
    assert types == ["execution_start", "eval_start", "eval_end"]


# ---------------------------------------------------------------------------
# Test 4: Multiple traces are separated
# ---------------------------------------------------------------------------


def test_multiple_traces_separated(log):
    log.log_event("TRC-X", "execution_start", {})
    log.log_event("TRC-Y", "failure", {})
    log.log_event("TRC-X", "execution_end", {})

    x_events = log.get_execution_timeline("TRC-X")
    y_events = log.get_execution_timeline("TRC-Y")

    assert len(x_events) == 2
    assert len(y_events) == 1
    assert all(e["trace_id"] == "TRC-X" for e in x_events)
    assert all(e["trace_id"] == "TRC-Y" for e in y_events)


# ---------------------------------------------------------------------------
# Test 5: Timestamps are non-empty and ordered within a trace
# ---------------------------------------------------------------------------


def test_timestamps_ordered_within_trace(log):
    for event_type in ["execution_start", "eval_start", "eval_end", "promotion_gate"]:
        log.log_event("TRC-TS", event_type, {})
    timeline = log.get_execution_timeline("TRC-TS")
    timestamps = [e["timestamp"] for e in timeline]
    assert all(t for t in timestamps), "Empty timestamp found"
    assert timestamps == sorted(timestamps), "Timestamps not ordered"


# ---------------------------------------------------------------------------
# Test 6: Unknown trace returns empty list
# ---------------------------------------------------------------------------


def test_unknown_trace_returns_empty_list(log):
    result = log.get_execution_timeline("NO-SUCH-TRACE")
    assert result == []


# ---------------------------------------------------------------------------
# Test 7: Unknown event_type raises ValueError
# ---------------------------------------------------------------------------


def test_unknown_event_type_raises(log):
    with pytest.raises(ValueError, match="Unknown event_type"):
        log.log_event("TRC-BAD", "made_up_event", {})


# ---------------------------------------------------------------------------
# RT-2.4: Complete pipeline trace timeline
# ---------------------------------------------------------------------------


def test_rt_complete_pipeline_timeline(log):
    trace = "TRC-PIPELINE"
    for et in ["admission_gate", "execution_start", "eval_start", "eval_end", "eval_gate", "promotion_gate"]:
        log.log_event(trace, et, {"stage": et})
    timeline = log.get_execution_timeline(trace)
    event_types = [e["event_type"] for e in timeline]
    assert "admission_gate" in event_types
    assert "execution_start" in event_types
    assert "promotion_gate" in event_types
    assert len(timeline) == 6


# ---------------------------------------------------------------------------
# RT-2.4: Thread-safety (concurrent writers)
# ---------------------------------------------------------------------------


def test_rt_thread_safety(log):
    errors = []

    def writer(trace_id, count):
        try:
            for _ in range(count):
                log.log_event(trace_id, "execution_start", {})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(f"TRC-T{i}", 20)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread errors: {errors}"
    assert log.event_count() == 100


# ---------------------------------------------------------------------------
# RT-2.4: query filter by event_type
# ---------------------------------------------------------------------------


def test_rt_query_filter_by_event_type(log):
    log.log_event("TRC-Q", "execution_start", {})
    log.log_event("TRC-Q", "failure", {"reason": "timeout"})
    log.log_event("TRC-Q", "execution_end", {})

    failures = log.query(trace_id="TRC-Q", event_type="failure")
    assert len(failures) == 1
    assert failures[0]["event_type"] == "failure"

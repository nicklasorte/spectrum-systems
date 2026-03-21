from spectrum_systems.modules.runtime.trace_emitter import (
    SPAN_STATUS_FAILURE,
    SPAN_STATUS_SUCCESS,
    add_event,
    end_span,
    start_span,
)


def test_start_span_initializes_required_fields() -> None:
    span = start_span(trace_id="trace-001", span_id="span-root", name="root")
    assert span["trace_id"] == "trace-001"
    assert span["span_id"] == "span-root"
    assert span["parent_span_id"] is None
    assert span["name"] == "root"
    assert span["status"] == SPAN_STATUS_SUCCESS
    assert isinstance(span["events"], list)


def test_span_nesting_records_parent_id() -> None:
    child = start_span(trace_id="trace-001", parent_span_id="span-root", name="child")
    assert child["parent_span_id"] == "span-root"


def test_add_event_appends_structured_event() -> None:
    span = start_span(trace_id="trace-001", name="root")
    add_event(span, event_name="validation_started", attributes={"artifact_id": "A-1"})
    assert len(span["events"]) == 1
    event = span["events"][0]
    assert event["event_name"] == "validation_started"
    assert event["attributes"]["artifact_id"] == "A-1"


def test_end_span_status_success() -> None:
    span = start_span(trace_id="trace-001", name="root")
    ended = end_span(span, status=SPAN_STATUS_SUCCESS)
    assert ended["status"] == SPAN_STATUS_SUCCESS
    assert ended["end_time"] is not None


def test_end_span_status_failure() -> None:
    span = start_span(trace_id="trace-001", name="root")
    ended = end_span(span, status=SPAN_STATUS_FAILURE)
    assert ended["status"] == SPAN_STATUS_FAILURE
    assert ended["end_time"] is not None

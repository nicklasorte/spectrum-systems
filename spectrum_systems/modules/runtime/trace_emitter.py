"""Deterministic trace span emission helpers for in-process validation flows."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

SPAN_STATUS_SUCCESS = "success"
SPAN_STATUS_FAILURE = "failure"

_VALID_STATUSES = frozenset({SPAN_STATUS_SUCCESS, SPAN_STATUS_FAILURE})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_id(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return str(uuid.uuid4())


def _coerce_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    return dict(attributes) if isinstance(attributes, dict) else {}


def start_span(
    *,
    trace_id: str,
    name: str,
    parent_span_id: str | None = None,
    span_id: str | None = None,
    start_time: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an open span dictionary for deterministic in-run mutation."""

    if not isinstance(trace_id, str) or not trace_id.strip():
        raise ValueError("start_span requires non-empty trace_id")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("start_span requires non-empty span name")

    return {
        "trace_id": trace_id,
        "span_id": _coerce_id(span_id),
        "parent_span_id": parent_span_id if isinstance(parent_span_id, str) and parent_span_id else None,
        "name": name,
        "start_time": start_time if isinstance(start_time, str) and start_time else _utc_now_iso(),
        "end_time": None,
        "status": SPAN_STATUS_SUCCESS,
        "attributes": _coerce_attributes(attributes),
        "events": [],
    }


def add_event(
    span: dict[str, Any],
    *,
    event_name: str,
    timestamp: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Append a structured event to an in-memory span dict."""

    if not isinstance(event_name, str) or not event_name.strip():
        raise ValueError("add_event requires non-empty event_name")

    span.setdefault("events", []).append(
        {
            "event_name": event_name,
            "timestamp": timestamp if isinstance(timestamp, str) and timestamp else _utc_now_iso(),
            "attributes": _coerce_attributes(attributes),
        }
    )


def end_span(
    span: dict[str, Any],
    *,
    status: str,
    end_time: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Finalize span status/timing and optionally merge terminal attributes."""

    if status not in _VALID_STATUSES:
        raise ValueError(f"end_span status must be one of {sorted(_VALID_STATUSES)}")

    if attributes:
        span.setdefault("attributes", {}).update(attributes)

    span["status"] = status
    span["end_time"] = end_time if isinstance(end_time, str) and end_time else _utc_now_iso()
    return span


__all__ = [
    "SPAN_STATUS_FAILURE",
    "SPAN_STATUS_SUCCESS",
    "add_event",
    "end_span",
    "start_span",
]

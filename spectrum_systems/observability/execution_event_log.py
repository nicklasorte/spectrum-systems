"""ExecutionEventLog: immutable, append-only execution event log.

All execution paths are logged here. Events cannot be modified after creation.
Supports per-trace timeline queries and filtering.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


VALID_EVENT_TYPES = frozenset({
    "admission_gate",
    "execution_start",
    "execution_end",
    "eval_start",
    "eval_end",
    "eval_gate",
    "failure",
    "promotion_gate",
    "lifecycle_transition",
    "justification_check",
})


class _ImmutableEvent(dict):
    """A dict that raises on item assignment after construction."""

    def __setitem__(self, key: Any, value: Any) -> None:
        raise TypeError("ExecutionEvent is immutable — no modifications allowed after creation")

    def __delitem__(self, key: Any) -> None:
        raise TypeError("ExecutionEvent is immutable — no deletions allowed")


class ExecutionEventLog:
    """Thread-safe, immutable append-only log of execution events.

    Each event is stamped with a monotonically increasing sequence number,
    ensuring ordering is deterministic even across rapid calls.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: List[_ImmutableEvent] = []
        self._trace_index: Dict[str, List[int]] = {}
        self._seq: int = 0

    def log_event(
        self,
        trace_id: str,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append an event. Returns the immutable event record."""
        if not trace_id:
            raise ValueError("trace_id is required")
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"Unknown event_type '{event_type}'. Valid: {sorted(VALID_EVENT_TYPES)}")

        with self._lock:
            self._seq += 1
            raw: Dict[str, Any] = {
                "event_id": f"EVT-{uuid.uuid4().hex[:12].upper()}",
                "seq": self._seq,
                "trace_id": trace_id,
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data or {},
            }
            event = _ImmutableEvent(raw)
            idx = len(self._events)
            self._events.append(event)
            self._trace_index.setdefault(trace_id, []).append(idx)

        return _ImmutableEvent(event)

    def get_execution_timeline(self, trace_id: str) -> List[Dict[str, Any]]:
        """Return ordered list of events for a trace_id. Empty list if unknown."""
        with self._lock:
            indices = self._trace_index.get(trace_id, [])
            return [dict(self._events[i]) for i in indices]

    def query(
        self,
        trace_id: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filter events by trace_id, event_type, or since (ISO timestamp)."""
        with self._lock:
            results = (dict(e) for e in self._events)

            if trace_id is not None:
                results = (e for e in results if e["trace_id"] == trace_id)
            if event_type is not None:
                results = (e for e in results if e["event_type"] == event_type)
            if since is not None:
                results = (e for e in results if e["timestamp"] >= since)

            return list(results)

    def all_traces(self) -> List[str]:
        """Return all known trace IDs."""
        with self._lock:
            return list(self._trace_index.keys())

    def event_count(self, trace_id: Optional[str] = None) -> int:
        with self._lock:
            if trace_id is None:
                return len(self._events)
            return len(self._trace_index.get(trace_id, []))

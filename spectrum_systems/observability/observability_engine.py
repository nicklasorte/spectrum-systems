"""Phase 4.1: Observability Engine

Ensure 100% event coverage for every execution.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

REQUIRED_EXECUTION_EVENTS = frozenset({
    "admission_gate",
    "execution_start",
    "execution_end",
    "eval_gate",
    "promotion_gate",
})


class ObservabilityEngine:
    """Track all execution events with 100% coverage guarantee."""

    def __init__(self) -> None:
        self._event_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def emit_event(
        self,
        trace_id: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Emit an execution event (immutable once appended)."""
        event: Dict[str, Any] = {
            "trace_id": trace_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": dict(data),
        }
        with self._lock:
            self._event_log.append(event)
        return event

    def get_execution_timeline(self, trace_id: str) -> List[Dict[str, Any]]:
        """Return all events for a trace in insertion order."""
        with self._lock:
            return [e for e in self._event_log if e["trace_id"] == trace_id]

    def validate_completeness(
        self, trace_id: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Validate that a trace has all required event types."""
        timeline = self.get_execution_timeline(trace_id)
        present = {e["event_type"] for e in timeline}
        missing = REQUIRED_EXECUTION_EVENTS - present

        if missing:
            return False, {
                "trace_id": trace_id,
                "completeness": False,
                "missing_events": sorted(missing),
            }

        return True, {
            "trace_id": trace_id,
            "completeness": True,
            "event_count": len(timeline),
        }

    def coverage_rate(self, trace_ids: List[str]) -> float:
        """Return fraction of traces with 100% event coverage."""
        if not trace_ids:
            return 1.0
        passing = sum(
            1 for tid in trace_ids if self.validate_completeness(tid)[0]
        )
        return passing / len(trace_ids)

    def clear(self) -> None:
        """Clear event log (for testing)."""
        with self._lock:
            self._event_log.clear()

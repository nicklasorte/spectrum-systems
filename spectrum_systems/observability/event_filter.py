"""Event log filtering for Phase 6: Event Log Optimization.

Filtering strategy — NOT removal:
- All events are stored in ExecutionEventLog
- Display is filtered by view type (debug / operator / monitoring)
- Events remain immutable and available for replay

Views:
  debug_view:      All events (for engineers debugging failures)
  operator_view:   Importance >= 3 (for operators monitoring health)
  monitoring_view: Category == monitoring (for dashboards and alerts)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# Event catalog: event_type → metadata
EVENT_CATALOG: Dict[str, Dict[str, Any]] = {
    "admission_gate": {
        "purpose": "Log when admission gate runs and its decision",
        "debug": True,
        "monitoring": True,
        "importance": 4,
        "category": "governance",
    },
    "execution_start": {
        "purpose": "Log when a PQX execution slice starts",
        "debug": True,
        "monitoring": False,
        "importance": 3,
        "category": "execution",
    },
    "execution_end": {
        "purpose": "Log when a PQX execution slice completes",
        "debug": True,
        "monitoring": True,
        "importance": 4,
        "category": "execution",
    },
    "eval_start": {
        "purpose": "Log when evaluation begins for an artifact",
        "debug": True,
        "monitoring": False,
        "importance": 2,
        "category": "evaluation",
    },
    "eval_end": {
        "purpose": "Log when evaluation completes",
        "debug": True,
        "monitoring": False,
        "importance": 2,
        "category": "evaluation",
    },
    "eval_gate": {
        "purpose": "Log eval gate decision and pass rate",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "category": "governance",
    },
    "failure": {
        "purpose": "Log a failure event with structured context",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "category": "monitoring",
    },
    "promotion_gate": {
        "purpose": "Log promotion gate decision",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "category": "governance",
    },
    "lifecycle_transition": {
        "purpose": "Log artifact lifecycle state transitions",
        "debug": True,
        "monitoring": True,
        "importance": 4,
        "category": "governance",
    },
    "justification_check": {
        "purpose": "Log system justification validation results",
        "debug": True,
        "monitoring": False,
        "importance": 2,
        "category": "evaluation",
    },
}

# Operator view threshold: show events with importance >= this value
OPERATOR_VIEW_THRESHOLD = 3


class EventFilter:
    """Filter events for different audiences — storage is never affected."""

    @staticmethod
    def debug_view(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Show all events. For engineers debugging failures."""
        return list(events)

    @staticmethod
    def operator_view(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Show only relevant events for operator health monitoring.

        Filters to events with importance >= OPERATOR_VIEW_THRESHOLD (3).
        """
        filtered = []
        for event in events:
            event_type = event.get("event_type", "")
            catalog_entry = EVENT_CATALOG.get(event_type, {})
            importance = catalog_entry.get("importance", 3)
            if importance >= OPERATOR_VIEW_THRESHOLD:
                filtered.append(event)
        return filtered

    @staticmethod
    def monitoring_view(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Show only monitoring-relevant events for dashboards/alerts."""
        filtered = []
        for event in events:
            event_type = event.get("event_type", "")
            catalog_entry = EVENT_CATALOG.get(event_type, {})
            if catalog_entry.get("monitoring", False):
                filtered.append(event)
        return filtered

    @staticmethod
    def failure_view(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Show only failure and blocked-gate events. For RCA."""
        failure_types = {"failure", "admission_gate", "eval_gate", "promotion_gate"}
        result = []
        for event in events:
            event_type = event.get("event_type", "")
            if event_type == "failure":
                result.append(event)
            elif event_type in failure_types:
                decision = event.get("data", {}).get("decision", "")
                if decision == "block":
                    result.append(event)
        return result

    @staticmethod
    def event_importance(event_type: str) -> int:
        """Return importance score for an event type (1-5)."""
        return EVENT_CATALOG.get(event_type, {}).get("importance", 3)

    @staticmethod
    def catalog_summary() -> Dict[str, Any]:
        """Return summary of event catalog for documentation."""
        return {
            "total_event_types": len(EVENT_CATALOG),
            "monitoring_events": [
                et for et, info in EVENT_CATALOG.items() if info.get("monitoring")
            ],
            "debug_only_events": [
                et for et, info in EVENT_CATALOG.items()
                if info.get("debug") and not info.get("monitoring")
            ],
            "high_importance_events": [
                et for et, info in EVENT_CATALOG.items()
                if info.get("importance", 0) >= 4
            ],
        }

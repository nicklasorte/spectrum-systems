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
    # Governance
    "admission_gate": {
        "purpose": "Log when admission gate runs and its decision",
        "debug": True,
        "monitoring": True,
        "importance": 4,
        "category": "governance",
    },
    "lifecycle_transition": {
        "purpose": "Log artifact lifecycle state transitions",
        "debug": True,
        "monitoring": True,
        "importance": 4,
        "category": "governance",
    },
    "promotion_gate": {
        "purpose": "Log promotion gate decision",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "category": "governance",
    },

    # Execution
    "execution_start": {
        "purpose": "Log when a PQX execution slice starts",
        "debug": True,
        "monitoring": False,
        "importance": 2,
        "category": "execution",
    },
    "execution_end": {
        "purpose": "Log when a PQX execution slice completes",
        "debug": True,
        "monitoring": True,
        "importance": 4,
        "category": "execution",
    },
    "execution_error": {
        "purpose": "Log execution failures with structured context",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "category": "execution",
    },

    # Evaluation
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
    "eval_gate_entry": {
        "purpose": "Gate evaluation start — low signal in normal operation",
        "debug": True,
        "monitoring": False,
        "importance": 2,
        "category": "evaluation",
    },
    "eval_gate_pass": {
        "purpose": "Gate evaluation passed — passes are expected, low signal",
        "debug": True,
        "monitoring": False,
        "importance": 1,
        "category": "evaluation",
    },
    "eval_gate_fail": {
        "purpose": "Gate evaluation failed — always surface to operators",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "category": "evaluation",
    },
    "justification_check": {
        "purpose": "Log system justification validation results",
        "debug": True,
        "monitoring": False,
        "importance": 2,
        "category": "evaluation",
    },

    # Control
    "control_decision": {
        "purpose": "CDE control decision emitted",
        "debug": True,
        "monitoring": True,
        "importance": 4,
        "category": "control",
    },
    "control_reversal": {
        "purpose": "CDE decision reversed — high-value signal",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "category": "control",
    },

    # Enforcement
    "enforce_start": {
        "purpose": "SEL enforcement action started",
        "debug": True,
        "monitoring": False,
        "importance": 2,
        "category": "enforcement",
    },
    "enforce_complete": {
        "purpose": "SEL enforcement action completed",
        "debug": True,
        "monitoring": True,
        "importance": 3,
        "category": "enforcement",
    },

    # Monitoring
    "failure": {
        "purpose": "Log a failure event with structured context",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "category": "monitoring",
    },

    # Debug-only — always filtered from operator/monitoring views
    "debug_context": {
        "purpose": "Debug context logging — developer use only",
        "debug": True,
        "monitoring": False,
        "importance": 1,
        "category": "debug",
    },
    "debug_trace": {
        "purpose": "Trace execution steps — developer use only",
        "debug": True,
        "monitoring": False,
        "importance": 1,
        "category": "debug",
    },
    "debug_state": {
        "purpose": "State snapshots — developer use only",
        "debug": True,
        "monitoring": False,
        "importance": 1,
        "category": "debug",
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
    def performance_view(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Show execution + enforcement events for performance timeline analysis."""
        performance_categories = {"execution", "monitoring"}
        result = []
        for event in events:
            event_type = event.get("event_type", "")
            catalog_entry = EVENT_CATALOG.get(event_type, {})
            category = catalog_entry.get("category", "")
            if category in performance_categories or event_type in {
                "execution_start", "execution_end", "execution_error",
                "enforce_start", "enforce_complete",
            }:
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


class RCAWithFiltering:
    """Connect event filtering to root-cause analysis (Phase 6 RCA integration).

    When diagnosing a failure, automatically surface the relevant events
    for that trace — unfiltered — so engineers see full context.
    """

    HIGH_IMPORTANCE_THRESHOLD = 3

    @staticmethod
    def events_for_trace(
        trace_id: str,
        all_events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return events scoped to a single trace, split by importance tier.

        High-importance events are shown by default; full log is available
        on demand. No data is discarded — this is filtering for display only.
        """
        relevant = [e for e in all_events if e.get("trace_id") == trace_id]
        high = [
            e for e in relevant
            if EventFilter.event_importance(e.get("event_type", ""))
            >= RCAWithFiltering.HIGH_IMPORTANCE_THRESHOLD
        ]
        return {
            "trace_id": trace_id,
            "default_view": high,
            "full_view": relevant,
            "default_count": len(high),
            "total_count": len(relevant),
            "message": (
                f"Showing {len(high)}/{len(relevant)} events. "
                "Switch to debug_view() to see all."
            ),
        }

    @staticmethod
    def rca_for_failure(
        failure: Dict[str, Any],
        all_events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Surface relevant events when an RCA guide references a failure."""
        trace_id = failure.get("trace_id", "")
        scoped = RCAWithFiltering.events_for_trace(trace_id, all_events)

        failure_events = [
            e for e in scoped["full_view"]
            if e.get("event_type") in {
                "execution_error", "eval_gate_fail", "control_reversal", "failure",
            }
        ]

        return {
            "failure_id": failure.get("artifact_id", "UNKNOWN"),
            "trace_id": trace_id,
            "failure_events": failure_events,
            "recommended_view": scoped["default_view"],
            "full_view_available": scoped["full_view"],
            "summary": scoped["message"],
        }

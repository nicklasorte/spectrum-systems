"""Event analysis and categorization for Phase 6: Event Log Optimization.

Analyzes which events are valuable, categorizes them, and measures the
usefulness improvement from filtering out low-signal noise.
"""

from __future__ import annotations

from typing import Any, Dict


# Full event taxonomy: event_type → classification metadata
EVENT_TAXONOMY: Dict[str, Dict[str, Any]] = {
    # Execution events
    "execution_start": {
        "category": "EXECUTION",
        "purpose": "Mark when a PQX execution slice starts",
        "debug": True,
        "monitoring": False,
        "importance": 2,
        "filter_by_default": True,
        "show_in_rca": True,
    },
    "execution_end": {
        "category": "EXECUTION",
        "purpose": "Mark when a PQX execution slice completes",
        "debug": True,
        "monitoring": True,
        "importance": 4,
        "filter_by_default": False,
        "show_in_rca": True,
    },
    "execution_error": {
        "category": "EXECUTION",
        "purpose": "Log execution failures with structured context",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "filter_by_default": False,
        "show_in_rca": True,
    },

    # Evaluation events
    "eval_gate_entry": {
        "category": "EVAL",
        "purpose": "Gate evaluation start",
        "debug": True,
        "monitoring": False,
        "importance": 2,
        "filter_by_default": True,
        "show_in_rca": True,
    },
    "eval_gate_pass": {
        "category": "EVAL",
        "purpose": "Gate evaluation passed",
        "debug": True,
        "monitoring": False,
        "importance": 1,
        "filter_by_default": True,
        "show_in_rca": False,
    },
    "eval_gate_fail": {
        "category": "EVAL",
        "purpose": "Gate evaluation failed — always surface",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "filter_by_default": False,
        "show_in_rca": True,
    },

    # Control events
    "control_decision": {
        "category": "CONTROL",
        "purpose": "Control decision emitted by CDE",
        "debug": True,
        "monitoring": True,
        "importance": 4,
        "filter_by_default": False,
        "show_in_rca": True,
    },
    "control_reversal": {
        "category": "CONTROL",
        "purpose": "CDE decision reversed — high-value signal",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "filter_by_default": False,
        "show_in_rca": True,
    },

    # Enforcement events
    "enforce_start": {
        "category": "ENFORCE",
        "purpose": "SEL enforcement action started",
        "debug": True,
        "monitoring": False,
        "importance": 2,
        "filter_by_default": True,
        "show_in_rca": True,
    },
    "enforce_complete": {
        "category": "ENFORCE",
        "purpose": "SEL enforcement action completed",
        "debug": True,
        "monitoring": True,
        "importance": 3,
        "filter_by_default": False,
        "show_in_rca": True,
    },

    # Governance / admission events
    "admission_gate": {
        "category": "GOVERNANCE",
        "purpose": "Log when admission gate runs and its decision",
        "debug": True,
        "monitoring": True,
        "importance": 4,
        "filter_by_default": False,
        "show_in_rca": True,
    },
    "lifecycle_transition": {
        "category": "GOVERNANCE",
        "purpose": "Log artifact lifecycle state transitions",
        "debug": True,
        "monitoring": True,
        "importance": 4,
        "filter_by_default": False,
        "show_in_rca": True,
    },
    "promotion_gate": {
        "category": "GOVERNANCE",
        "purpose": "Log promotion gate decision",
        "debug": True,
        "monitoring": True,
        "importance": 5,
        "filter_by_default": False,
        "show_in_rca": True,
    },

    # Debug-only events (filtered from operator/monitoring views)
    "debug_context": {
        "category": "DEBUG",
        "purpose": "Debug context logging — developer use only",
        "debug": True,
        "monitoring": False,
        "importance": 1,
        "filter_by_default": True,
        "show_in_rca": False,
    },
    "debug_trace": {
        "category": "DEBUG",
        "purpose": "Trace execution steps — developer use only",
        "debug": True,
        "monitoring": False,
        "importance": 1,
        "filter_by_default": True,
        "show_in_rca": False,
    },
    "debug_state": {
        "category": "DEBUG",
        "purpose": "State snapshots — developer use only",
        "debug": True,
        "monitoring": False,
        "importance": 1,
        "filter_by_default": True,
        "show_in_rca": False,
    },
}

# Baseline usefulness from Phase 1 measurement
_BASELINE_USEFULNESS = 0.65


class EventAnalysis:
    """Categorize and measure event usefulness across the execution loop."""

    def get_taxonomy(self) -> Dict[str, Dict[str, Any]]:
        return dict(EVENT_TAXONOMY)

    def usefulness_report(self) -> Dict[str, Any]:
        """Calculate event usefulness improvement from filtering noise.

        Baseline: 65% useful (Phase 1 measurement)
        Method: filter events with filter_by_default=True from default views.

        Usefulness in operator view = fraction of retained events that are
        high-value (monitoring=True or importance >= 4). Low-signal events
        (importance <= 2, debug-only) are filtered from display but kept in
        storage — no data is lost.
        """
        all_events = EVENT_TAXONOMY
        total = len(all_events)
        filtered_count = sum(1 for e in all_events.values() if e["filter_by_default"])
        retained_count = total - filtered_count

        # High-value retained: events shown in operator view that carry signal
        high_value_retained = sum(
            1 for e in all_events.values()
            if not e["filter_by_default"]
            and (e.get("monitoring") or e["importance"] >= 4)
        )

        filter_ratio = filtered_count / total
        improved = high_value_retained / retained_count if retained_count > 0 else 0.0

        return {
            "baseline_usefulness": _BASELINE_USEFULNESS,
            "total_event_types": total,
            "filtered_by_default": filtered_count,
            "retained_in_operator_view": retained_count,
            "filter_percentage": round(filter_ratio * 100, 1),
            "improved_usefulness": round(improved, 3),
            "improvement_delta": round(improved - _BASELINE_USEFULNESS, 3),
            "target_met": improved >= 0.90,
        }

    def events_for_rca(self) -> Dict[str, Dict[str, Any]]:
        """Return events that should surface automatically during RCA."""
        return {k: v for k, v in EVENT_TAXONOMY.items() if v["show_in_rca"]}

    def events_by_category(self) -> Dict[str, list]:
        """Group event types by category."""
        result: Dict[str, list] = {}
        for name, meta in EVENT_TAXONOMY.items():
            cat = meta["category"]
            result.setdefault(cat, []).append(name)
        return result

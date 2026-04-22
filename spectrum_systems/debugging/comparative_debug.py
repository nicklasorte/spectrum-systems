"""
Phase 8: Comparative Debugging

Compare two divergent execution runs side-by-side.
Find exactly where they diverge.
"""

from typing import Dict, List
from pathlib import Path
import json


class ComparativeDebugger:
    """Compare two divergent execution runs side-by-side."""

    def __init__(self):
        self.comparisons = {}

    def get_event_log(self, trace_id: str, event_store: str = "/tmp/artifacts") -> List[Dict]:
        """Retrieve event log for a trace."""
        log_file = Path(event_store) / f"events_{trace_id}.json"
        if log_file.exists():
            with open(log_file) as f:
                return json.load(f)
        return []

    def compare_runs(self, trace_a: str, trace_b: str, event_store: str = "/tmp/artifacts") -> Dict:
        """
        Find differences between two execution runs.

        Returns:
            - differences: list of divergences
            - divergence_index: first point where they differ
            - common_events: number of matching events before divergence
        """
        events_a = self.get_event_log(trace_a, event_store)
        events_b = self.get_event_log(trace_b, event_store)

        differences = []
        divergence_index = None

        for i, (event_a, event_b) in enumerate(zip(events_a, events_b)):
            if event_a.get("event_type") != event_b.get("event_type"):
                differences.append({
                    "event_index": i,
                    "type": "event_type_mismatch",
                    "a_type": event_a.get("event_type"),
                    "b_type": event_b.get("event_type"),
                })
                if divergence_index is None:
                    divergence_index = i

            if event_a.get("data") != event_b.get("data"):
                differences.append({
                    "event_index": i,
                    "type": "data_divergence",
                    "a_data": event_a.get("data"),
                    "b_data": event_b.get("data"),
                })
                if divergence_index is None:
                    divergence_index = i

            if event_a.get("artifact_id") != event_b.get("artifact_id"):
                differences.append({
                    "event_index": i,
                    "type": "artifact_divergence",
                    "a_artifact": event_a.get("artifact_id"),
                    "b_artifact": event_b.get("artifact_id"),
                })
                if divergence_index is None:
                    divergence_index = i

        if len(events_a) != len(events_b):
            differences.append({
                "type": "length_mismatch",
                "a_length": len(events_a),
                "b_length": len(events_b),
            })

        return {
            "trace_a": trace_a,
            "trace_b": trace_b,
            "common_events": divergence_index if divergence_index is not None else len(events_a),
            "divergence_index": divergence_index,
            "total_differences": len(differences),
            "differences": differences,
        }

    def trace_to_divergence_point(self, comparison: Dict, event_store: str = "/tmp/artifacts") -> Dict:
        """What led to the first difference?"""
        if comparison["divergence_index"] is None:
            return {"status": "identical", "message": "Runs are identical"}

        idx = comparison["divergence_index"]
        trace_a = comparison["trace_a"]

        events = self.get_event_log(trace_a, event_store)

        preceding = events[idx - 1] if idx > 0 else None

        return {
            "divergence_at": idx,
            "preceding_event": preceding,
            "first_difference": comparison["differences"][0] if comparison["differences"] else None,
        }

"""
DriftTrace: End-to-end trace of drift detection through all pipeline stages.
Surfaces bottlenecks and gaps that would otherwise require log archaeology.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional


@dataclass
class TraceStep:
    """One stage in the drift detection pipeline trace."""
    step_number: int
    system: str
    action: str
    timestamp: datetime
    node: str
    duration_ms: float
    metadata: Dict = field(default_factory=dict)


# Canonical 7-stage pipeline for drift detection.
_PIPELINE_STAGES = [
    "Metrics Collection",
    "Metrics Aggregation",
    "Baseline Comparison",
    "Consensus Check",
    "Alert Generation",
    "Notification",
    "Exception Handling",
]


class DriftTrace:
    """Trace drift detection end-to-end through all 7 pipeline stages."""

    def trace_drift_detection(self, drift_event: Dict) -> List[TraceStep]:
        """
        Produce a 7-step trace for a drift event.

        In production this would reconstruct steps from distributed trace spans.
        Here we build a representative trace from the event's context fields so
        the data structure is fully exercisable in tests and tooling.
        """
        trace_id = drift_event.get("trace_id", str(uuid.uuid4()))
        detection_time = self._parse_dt(drift_event.get("detection_time"))
        node = drift_event.get("primary_node", drift_event.get("region", "node-primary"))
        metric = drift_event.get("metric", "unknown")
        service = drift_event.get("service", "unknown")
        nodes = drift_event.get("detection_nodes", [node])
        agreement = drift_event.get("agreement_percentage", 100.0)

        # Reconstruct approximate step start times by working backwards from detection.
        # Typical pipeline latency breakdown (ms):
        #   collection: 200, aggregation: 300, comparison: 150,
        #   consensus: 400, alert: 100, notification: 80, exception: 250
        latencies = [200.0, 300.0, 150.0, 400.0, 100.0, 80.0, 250.0]
        total_latency_ms = sum(latencies)
        pipeline_start = detection_time - timedelta(milliseconds=total_latency_ms)

        steps: List[TraceStep] = []
        current_time = pipeline_start

        stage_metadata = [
            {
                "metric": metric,
                "source": f"{service}.metrics",
                "collection_interval_ms": 60000,
                "trace_id": trace_id,
            },
            {
                "window_size_seconds": 300,
                "aggregation_function": "avg",
                "sample_count": 5,
            },
            {
                "baseline_value": drift_event.get("baseline_value", 0.0),
                "current_value": drift_event.get("current_value", 0.0),
                "threshold": drift_event.get("threshold", 0.0),
                "exceeded": True,
            },
            {
                "nodes_polled": len(nodes),
                "nodes_agreeing": round(len(nodes) * agreement / 100),
                "agreement_pct": agreement,
                "quorum_required": 80.0,
            },
            {
                "severity": drift_event.get("severity", "MEDIUM"),
                "alert_id": str(uuid.uuid4()),
                "channels": ["pagerduty", "slack"],
            },
            {
                "recipients": ["on-call-engineer"],
                "delivery_status": "delivered",
            },
            {
                "exception_artifact_id": str(uuid.uuid4()),
                "handler": "drift_remediation_enforcer",
                "action": "open_exception",
            },
        ]

        stage_actions = [
            f"Collect raw {metric} samples from {service}",
            f"Aggregate {metric} samples over 5-minute window",
            f"Compare aggregated {metric} to baseline",
            f"Poll {len(nodes)} node(s) for consensus on drift status",
            "Generate drift alert artifact",
            "Notify on-call engineer",
            "Open exception artifact and route to remediation handler",
        ]

        for i, (stage, action, latency_ms, meta) in enumerate(
            zip(_PIPELINE_STAGES, stage_actions, latencies, stage_metadata), start=1
        ):
            steps.append(TraceStep(
                step_number=i,
                system=stage,
                action=action,
                timestamp=current_time,
                node=nodes[i % len(nodes)] if nodes else node,
                duration_ms=latency_ms,
                metadata=meta,
            ))
            current_time = current_time + timedelta(milliseconds=latency_ms)

        return steps

    def get_bottleneck(self, trace: List[TraceStep]) -> str:
        """Return the name of the slowest step in the trace."""
        if not trace:
            return "no trace steps available"
        slowest = max(trace, key=lambda s: s.duration_ms)
        return (
            f"Step {slowest.step_number} ({slowest.system}): "
            f"{slowest.duration_ms:.0f}ms — {slowest.action}"
        )

    def get_critical_path(self, trace: List[TraceStep]) -> List[TraceStep]:
        """
        Return the critical path — steps whose cumulative latency dominates total time.
        Simple heuristic: steps that together account for ≥80% of total duration.
        """
        if not trace:
            return []

        total_ms = sum(s.duration_ms for s in trace)
        target_ms = total_ms * 0.80

        sorted_steps = sorted(trace, key=lambda s: s.duration_ms, reverse=True)
        critical: List[TraceStep] = []
        accumulated = 0.0

        for step in sorted_steps:
            critical.append(step)
            accumulated += step.duration_ms
            if accumulated >= target_ms:
                break

        return sorted(critical, key=lambda s: s.step_number)

    @staticmethod
    def _parse_dt(value) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.rstrip("Z"))
            except ValueError:
                pass
        return datetime.utcnow()

"""
ContextCapture: Automatically assembles complete DriftContext from a raw drift event.
Every field required for RCA is captured at detection time so engineers never chase data.
"""

import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class DriftContext:
    """Complete context snapshot for one drift event."""
    drift_id: str
    timestamp: datetime

    # WHAT drifted
    signal: str
    metric: str
    region: str
    service: str

    # HOW MUCH
    baseline_value: float
    current_value: float
    change_percent: float
    threshold: float
    severity: str

    # WHEN
    detection_time: datetime
    last_good_time: datetime
    duration_minutes: float

    # WHERE (distributed)
    detection_nodes: List[str]
    agreement_percentage: float

    # SIMILAR CASES
    similar_past_drifts: List[Dict]

    # CORRELATED SIGNALS
    correlated_degradations: List[str]

    # DEBUG INFO
    raw_metrics_window: str
    detection_logs: str
    trace_id: str


def _now() -> datetime:
    return datetime.utcnow()


def _parse_dt(value, fallback: Optional[datetime] = None) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.rstrip("Z"))
        except ValueError:
            pass
    return fallback or _now()


class ContextCapture:
    """Automatically capture full drift context from a raw drift event dict."""

    def capture(self, drift_event: Dict) -> DriftContext:
        """
        Produce a DriftContext from a raw drift detection payload.

        Accepts any subset of the canonical drift event schema; missing fields
        are filled with safe defaults so context is always complete.
        """
        baseline = float(drift_event.get("baseline_value", 0.0))
        current = float(drift_event.get("current_value", 0.0))
        change_pct = self._change_percent(baseline, current)

        detection_time = _parse_dt(drift_event.get("detection_time"))
        last_good_time = _parse_dt(
            drift_event.get("last_good_time"),
            fallback=detection_time,
        )
        duration_minutes = (detection_time - last_good_time).total_seconds() / 60

        nodes = drift_event.get("detection_nodes", [])
        if isinstance(nodes, str):
            nodes = [nodes]

        return DriftContext(
            drift_id=drift_event.get("drift_id", str(uuid.uuid4())),
            timestamp=_parse_dt(drift_event.get("timestamp")),
            signal=drift_event.get("signal", drift_event.get("signal_type", "unknown")),
            metric=drift_event.get("metric", "unknown"),
            region=drift_event.get("region", "unknown"),
            service=drift_event.get("service", "unknown"),
            baseline_value=baseline,
            current_value=current,
            change_percent=change_pct,
            threshold=float(drift_event.get("threshold", 0.0)),
            severity=drift_event.get("severity", "MEDIUM"),
            detection_time=detection_time,
            last_good_time=last_good_time,
            duration_minutes=round(duration_minutes, 2),
            detection_nodes=nodes,
            agreement_percentage=float(drift_event.get("agreement_percentage", 100.0)),
            similar_past_drifts=drift_event.get("similar_past_drifts", []),
            correlated_degradations=drift_event.get("correlated_degradations", []),
            raw_metrics_window=drift_event.get("raw_metrics_window", ""),
            detection_logs=drift_event.get("detection_logs", ""),
            trace_id=drift_event.get("trace_id", str(uuid.uuid4())),
        )

    def to_dict(self, context: DriftContext) -> Dict:
        """Serialize DriftContext to a plain dict (datetimes as ISO strings)."""
        d = asdict(context)
        d["timestamp"] = context.timestamp.isoformat() + "Z"
        d["detection_time"] = context.detection_time.isoformat() + "Z"
        d["last_good_time"] = context.last_good_time.isoformat() + "Z"
        return d

    @staticmethod
    def _change_percent(baseline: float, current: float) -> float:
        if baseline == 0:
            return 0.0
        return round(((current - baseline) / abs(baseline)) * 100, 2)

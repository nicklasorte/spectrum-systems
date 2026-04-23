"""
DriftMetrics: Tracks all 6 key debuggability metrics from Phase 1 baseline through target.
Provides progress visibility so the team knows when the optimization is complete.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class Metric:
    """One tracked metric with baseline, target, and unit."""
    name: str
    baseline: float
    target: float
    unit: str

    @property
    def improvement_percent(self) -> float:
        if self.baseline == 0:
            return 0.0
        return round((self.target - self.baseline) / abs(self.baseline) * 100, 1)


@dataclass
class Measurement:
    """One recorded measurement for a metric."""
    metric_name: str
    value: float
    timestamp: datetime


class DriftMetrics:
    """Track all 6 drift debuggability metrics from Phase 1."""

    def __init__(self):
        self.metrics = self._initialize_metrics()
        self.measurements: List[Measurement] = []

    def _initialize_metrics(self) -> Dict[str, Metric]:
        """
        Six metrics from Phase 1 baseline analysis.
        Baseline → Target pairs represent the full optimization goal.
        """
        return {
            "rca_time_minutes": Metric(
                name="rca_time_minutes",
                baseline=25.0,
                target=10.0,
                unit="minutes",
            ),
            "new_engineer_debug_time": Metric(
                name="new_engineer_debug_time",
                baseline=40.0,
                target=15.0,
                unit="minutes",
            ),
            "false_positive_clarity": Metric(
                name="false_positive_clarity",
                baseline=30.0,
                target=85.0,
                unit="percent",
            ),
            "silent_drift_detection": Metric(
                name="silent_drift_detection",
                baseline=65.0,
                target=95.0,
                unit="percent",
            ),
            "distributed_agreement": Metric(
                name="distributed_agreement",
                baseline=92.0,
                target=99.0,
                unit="percent",
            ),
            "operator_confidence": Metric(
                name="operator_confidence",
                baseline=6.2,
                target=9.0,
                unit="score_out_of_10",
            ),
        }

    def record_measurement(self, metric_name: str, value: float, timestamp: Optional[datetime] = None) -> None:
        """Record a measurement for a metric."""
        if metric_name not in self.metrics:
            raise KeyError(f"Unknown metric: '{metric_name}'")
        self.measurements.append(Measurement(
            metric_name=metric_name,
            value=value,
            timestamp=timestamp or datetime.utcnow(),
        ))

    def get_latest(self, metric_name: str) -> Optional[float]:
        """Return the most recent recorded value for a metric."""
        relevant = [m.value for m in self.measurements if m.metric_name == metric_name]
        return relevant[-1] if relevant else None

    def get_progress(self, metric_name: str) -> Dict:
        """Return progress toward target for one metric."""
        if metric_name not in self.metrics:
            raise KeyError(f"Unknown metric: '{metric_name}'")
        metric = self.metrics[metric_name]
        latest = self.get_latest(metric_name)

        if latest is None:
            return {
                "metric": metric_name,
                "baseline": metric.baseline,
                "target": metric.target,
                "current": None,
                "progress_pct": 0.0,
                "on_track": False,
            }

        total_change_needed = metric.target - metric.baseline
        achieved = latest - metric.baseline

        if total_change_needed == 0:
            progress_pct = 100.0
        else:
            progress_pct = round((achieved / total_change_needed) * 100, 1)

        # on_track: moving in the right direction and >= 50% of the way there
        right_direction = (achieved >= 0) if metric.target >= metric.baseline else (achieved <= 0)
        on_track = right_direction and abs(progress_pct) >= 50

        return {
            "metric": metric_name,
            "baseline": metric.baseline,
            "target": metric.target,
            "current": latest,
            "progress_pct": progress_pct,
            "on_track": on_track,
        }

    def all_metrics_on_track(self) -> bool:
        """Return True only if every metric with a recorded measurement is on track."""
        for name in self.metrics:
            if self.get_latest(name) is not None:
                if not self.get_progress(name)["on_track"]:
                    return False
        return True

    def summary(self) -> List[Dict]:
        """Return a summary row for every metric."""
        return [self.get_progress(name) for name in self.metrics]

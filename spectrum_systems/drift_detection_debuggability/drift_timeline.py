"""
DriftTimeline: ASCII timeline showing metric evolution from baseline through drift detection.
Helps engineers instantly see when degradation started and how fast it progressed.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .drift_context import DriftContext


@dataclass
class TimelinePoint:
    """One data point on the drift timeline."""
    timestamp: datetime
    value: float
    baseline: float
    percent_change: float
    status: str  # "baseline", "degrading", "drifted", "detected"


_BAR_WIDTH = 12
_BAR_CHAR = "█"   # full block
_EMPTY_CHAR = "░"  # light shade


class DriftTimeline:
    """Visual ASCII timeline of metric evolution from baseline to drift detection."""

    def generate_timeline(self, context: DriftContext) -> str:
        """
        Generate a readable ASCII timeline from context.

        The timeline synthesises a representative set of points across three phases:
        baseline, degradation, and drift/detection. In production this would be
        populated from the raw_metrics_window; here we model the phases from
        the scalar summary values in DriftContext.
        """
        points = self._synthesize_points(context)
        if not points:
            return "(no timeline data available)"

        phases = self._identify_phases([(p.timestamp, p.value) for p in points])
        lines = []
        current_phase = None

        for point in points:
            phase = point.status
            if phase != current_phase:
                current_phase = phase
                lines.append("")
                if phase == "baseline":
                    lines.append("Baseline period:")
                elif phase == "degrading":
                    lines.append("Degradation starts:")
                elif phase in ("drifted", "detected"):
                    lines.append("Drift detected:")

            bar = self._render_bar(point.value, context.baseline_value)
            ts = point.timestamp.strftime("%H:%M")
            marker = " <- ALERT FIRED" if phase == "detected" else ""
            pct = f"({point.percent_change:+.1f}%)" if phase != "baseline" else ""
            lines.append(f"  {ts} {bar} {point.value:.1f} {pct}{marker}")

        return "\n".join(lines).strip()

    def identify_phases(self, metrics: List[Tuple[datetime, float]]) -> Dict:
        """
        Identify baseline, degradation, and drift phases from a metric series.

        Returns a dict with keys: baseline_end, degradation_start, drift_start.
        Thresholds: degradation = >5% change, drift = >10% change from first value.
        """
        return self._identify_phases(metrics)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _synthesize_points(self, context: DriftContext) -> List[TimelinePoint]:
        """
        Build a representative timeline from the scalar summary in DriftContext.
        Produces 9 points across three phases so the display is always populated.
        """
        import math

        baseline = context.baseline_value
        current = context.current_value
        detection_time = context.detection_time
        last_good = context.last_good_time

        total_seconds = max((detection_time - last_good).total_seconds(), 60)
        step = total_seconds / 8  # 9 points: indices 0..8

        points: List[TimelinePoint] = []

        for i in range(9):
            ts = datetime(*last_good.timetuple()[:6]) if i == 0 else \
                datetime.utcfromtimestamp(last_good.timestamp() + i * step)

            # Linear interpolation from baseline toward current value
            fraction = i / 8
            # First 3 points are stable baseline, then linear degradation
            if i < 3:
                value = baseline
                status = "baseline"
                pct = 0.0
            else:
                value = baseline + (current - baseline) * ((fraction - 0.375) / 0.625)
                value = max(value, min(baseline, current)) if current < baseline else \
                        min(value, max(baseline, current))
                pct = ((value - baseline) / abs(baseline) * 100) if baseline != 0 else 0.0
                abs_pct = abs(pct)
                if abs_pct < 5:
                    status = "baseline"
                elif abs_pct < 10:
                    status = "degrading"
                elif i < 8:
                    status = "drifted"
                else:
                    status = "detected"

            points.append(TimelinePoint(
                timestamp=ts,
                value=round(value, 1),
                baseline=baseline,
                percent_change=round(pct, 1),
                status=status,
            ))

        return points

    def _identify_phases(self, metrics: List[Tuple[datetime, float]]) -> Dict:
        if not metrics:
            return {"baseline_end": None, "degradation_start": None, "drift_start": None}

        first_value = metrics[0][1]
        baseline_end = None
        degradation_start = None
        drift_start = None

        for ts, value in metrics:
            if first_value == 0:
                break
            pct = abs((value - first_value) / first_value * 100)
            if pct >= 10 and drift_start is None:
                drift_start = ts
            if pct >= 5 and degradation_start is None:
                degradation_start = ts
            if pct < 2:
                baseline_end = ts

        return {
            "baseline_end": baseline_end,
            "degradation_start": degradation_start,
            "drift_start": drift_start,
        }

    def _render_bar(self, value: float, baseline: float) -> str:
        """Render a _BAR_WIDTH-character bar proportional to value/baseline ratio."""
        if baseline == 0:
            ratio = 1.0
        else:
            ratio = min(max(value / baseline, 0.0), 1.0) if value < baseline else \
                    min(max(baseline / value, 0.0), 1.0)
        filled = round(ratio * _BAR_WIDTH)
        empty = _BAR_WIDTH - filled
        return _BAR_CHAR * filled + _EMPTY_CHAR * empty

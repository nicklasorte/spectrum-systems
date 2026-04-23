"""
DriftFailureModeRegistry: Documents all 6 drift failure modes from Phase 1 analysis.
Baseline RCA times: 25-30 minutes average across all modes.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class DriftFailureMode:
    """Represents one way drift detection can fail."""
    name: str
    description: str
    cause: str
    symptom: str
    severity: str  # CRITICAL, HIGH, MEDIUM
    rca_difficulty: str
    current_rca_time_min: int
    current_rca_time_max: int


class DriftFailureModeRegistry:
    """Registry of all 6 drift failure modes from Phase 1 analysis."""

    def __init__(self):
        self.modes = self._initialize_modes()

    def _initialize_modes(self) -> List[DriftFailureMode]:
        return [
            DriftFailureMode(
                name="silent_drift_undetected",
                description="Drift occurs but no signal is emitted; system appears healthy",
                cause="Threshold set too high, metric aggregation masks signal, or detection node offline",
                symptom="Downstream degradation without preceding drift alert",
                severity="CRITICAL",
                rca_difficulty="HARD",
                current_rca_time_min=30,
                current_rca_time_max=45,
            ),
            DriftFailureMode(
                name="false_positive_drift",
                description="Drift signal fired but underlying metric is within acceptable range",
                cause="Threshold too sensitive, transient spike, or noisy baseline period",
                symptom="Alert fires but manual inspection shows no real degradation",
                severity="MEDIUM",
                rca_difficulty="MEDIUM",
                current_rca_time_min=15,
                current_rca_time_max=20,
            ),
            DriftFailureMode(
                name="delayed_drift_detection",
                description="Drift is real but signal arrives 10+ minutes after onset",
                cause="Aggregation window too large, polling interval too long, or backpressure in pipeline",
                symptom="Alert fires long after issue is already visible in dashboards",
                severity="HIGH",
                rca_difficulty="MEDIUM",
                current_rca_time_min=20,
                current_rca_time_max=25,
            ),
            DriftFailureMode(
                name="exception_handling_fails",
                description="Drift detected but exception_handling pipeline fails to trigger remediation",
                cause="Exception artifact malformed, routing misconfigured, or SEL in frozen state",
                symptom="Drift signal present but no remediation action taken; exception queue grows",
                severity="CRITICAL",
                rca_difficulty="HARD",
                current_rca_time_min=25,
                current_rca_time_max=35,
            ),
            DriftFailureMode(
                name="exception_resolution_incomplete",
                description="Exception opened but closed without full root cause resolution",
                cause="Operator closed exception prematurely, or resolution criteria not enforced",
                symptom="Drift recurs within hours of exception closure",
                severity="HIGH",
                rca_difficulty="MEDIUM",
                current_rca_time_min=20,
                current_rca_time_max=30,
            ),
            DriftFailureMode(
                name="distributed_detection_disagreement",
                description="Detection nodes disagree on whether drift is present",
                cause="Clock skew between nodes, inconsistent metric sources, or network partition",
                symptom="Some nodes report drift, others report no_drift for the same time window",
                severity="CRITICAL",
                rca_difficulty="VERY_HARD",
                current_rca_time_min=40,
                current_rca_time_max=60,
            ),
        ]

    def get_average_rca_time(self) -> float:
        """Calculate average RCA time (midpoint of each range) across all modes."""
        if not self.modes:
            return 0.0
        midpoints = [(m.current_rca_time_min + m.current_rca_time_max) / 2 for m in self.modes]
        return sum(midpoints) / len(midpoints)

    def get_by_severity(self, severity: str) -> List[DriftFailureMode]:
        """Get all failure modes of a given severity."""
        return [m for m in self.modes if m.severity == severity]

    def get_by_name(self, name: str) -> DriftFailureMode:
        """Get a failure mode by name."""
        for mode in self.modes:
            if mode.name == name:
                return mode
        raise KeyError(f"No failure mode named '{name}'")

"""
Observability Module — spectrum_systems/modules/observability/

Provides the system-wide observability layer for measuring performance,
grounding quality, human disagreement, latency, and deterministic failure
controls across the full AI workflow.

Sub-modules
-----------
metrics
    ObservabilityRecord data model and MetricsStore persistence layer.
aggregation
    Aggregation functions for pass metrics, error distributions,
    grounding failure rates, and human disagreement rates.
trends
    Run-over-run trend tracking and delta computation.
failure_ranking
    Failure-first ranking functions for worst cases and weak components.
failure_enforcement
    BB+1 deterministic control decisions from failure-first metrics.
"""

from spectrum_systems.modules.observability.failure_enforcement import (
    classify_incident_severity,
    derive_system_response,
    enforce_component_controls,
    evaluate_failure_controls,
)

__all__ = [
    "evaluate_failure_controls",
    "enforce_component_controls",
    "derive_system_response",
    "classify_incident_severity",
]

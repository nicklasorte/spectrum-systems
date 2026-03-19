"""
Observability Module — spectrum_systems/modules/observability/

Provides the system-wide observability layer for measuring performance,
grounding quality, human disagreement, and latency across the full
AI workflow.

Sub-modules
-----------
metrics
    ObservabilityRecord data model and MetricsStore persistence layer.
aggregation
    Aggregation functions for pass metrics, error distributions,
    grounding failure rates, human disagreement rates, and BB
    failure-first derived metrics.
trends
    Run-over-run trend tracking and delta computation.
failure_ranking
    BB — Failure-First detection and ranking functions.  Surfaces
    dangerous promotes, high-confidence errors, worst cases, and
    pass weaknesses.
"""

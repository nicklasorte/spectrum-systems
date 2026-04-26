"""TLS dependency-graph and prioritization module.

This module is artifact-first, deterministic, and **observer-only**: every
public function reads or writes governed JSON artifacts whose schemas live in
``schemas/artifacts``. There is no model-based ranking. The module owns no
closure, advancement, or compliance authority — outputs are
visualization/analysis inputs (recommendation_signal artifacts) consumed by
canonical owners (CDE / GOV / SEL / PRA) which retain all closure,
advancement, and compliance authority.

Pipeline (TLS-STACK-01):

    Phase 0 (TLS-00) registry_parser   -> system_registry_dependency_graph.json
    Phase 1 (TLS-01) evidence_scanner  -> system_evidence_attachment.json
    Phase 2 (TLS-02) classification    -> system_candidate_classification.json
    Phase 3 (TLS-03) trust_gaps        -> system_trust_gap_report.json
    Phase 4 (TLS-04) ranking           -> system_dependency_priority_report.json

Each phase is fail-closed: missing inputs / parse errors raise instead of
silently returning empty results.
"""

from .registry_parser import (
    DependencyGraph,
    SystemNode,
    build_dependency_graph,
    parse_registry,
    validate_dependency_graph,
)

__all__ = [
    "DependencyGraph",
    "SystemNode",
    "build_dependency_graph",
    "parse_registry",
    "validate_dependency_graph",
]

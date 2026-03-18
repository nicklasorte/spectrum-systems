"""
Impact Scoring — spectrum_systems/modules/error_taxonomy/impact.py

Computes weighted severity scores for individual classification records and
aggregates them across clusters to surface the highest-impact failure patterns.

Design principles
-----------------
- Severity weights are configurable but default to the problem spec.
- Scoring is fully deterministic.
- Cluster ranking uses a stable multi-key sort.

Public API
----------
SEVERITY_WEIGHTS
    Default mapping of severity label → numeric weight.

compute_weighted_severity(record, catalog) -> float
    Weighted score for a single ErrorClassificationRecord.

compute_cluster_impact(cluster) -> float
    Sum of weighted_severity across the cluster's metric.

rank_clusters(clusters) -> List[ErrorCluster]
    Return clusters sorted by (weighted_severity_score DESC,
    record_count DESC, avg_confidence DESC).
"""
from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog
    from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord
    from spectrum_systems.modules.error_taxonomy.clustering import ErrorCluster

# ---------------------------------------------------------------------------
# Severity weights (configurable)
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS: Dict[str, float] = {
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
    "critical": 5.0,
}


# ---------------------------------------------------------------------------
# Per-record scoring
# ---------------------------------------------------------------------------

def compute_weighted_severity(
    record: "ErrorClassificationRecord",
    catalog: "ErrorTaxonomyCatalog",
    weights: Dict[str, float] | None = None,
) -> float:
    """Compute the weighted severity score for a single classification record.

    Score = sum over each classification entry of (severity_weight × confidence).

    Parameters
    ----------
    record:
        An ``ErrorClassificationRecord``.
    catalog:
        Loaded ``ErrorTaxonomyCatalog`` for severity lookup.
    weights:
        Optional override for severity weights.  Defaults to
        ``SEVERITY_WEIGHTS``.

    Returns
    -------
    float
        Non-negative weighted severity score.
    """
    _weights = weights or SEVERITY_WEIGHTS
    total = 0.0
    for entry in record.classifications:
        code = entry["error_code"]
        confidence = float(entry.get("confidence", 1.0))
        subtype = catalog.get_error(code)
        severity = subtype.default_severity if subtype else "medium"
        weight = _weights.get(severity, 2.0)
        total += weight * confidence
    return total


# ---------------------------------------------------------------------------
# Cluster-level scoring
# ---------------------------------------------------------------------------

def compute_cluster_impact(cluster: "ErrorCluster") -> float:
    """Return the pre-computed weighted severity score from a cluster's metrics.

    Parameters
    ----------
    cluster:
        An ``ErrorCluster`` instance.

    Returns
    -------
    float
        The ``weighted_severity_score`` stored in the cluster's metrics.
    """
    return cluster.metrics["weighted_severity_score"]


# ---------------------------------------------------------------------------
# Cluster ranking
# ---------------------------------------------------------------------------

def rank_clusters(clusters: List["ErrorCluster"]) -> List["ErrorCluster"]:
    """Sort clusters by impact, largest first.

    Sort key (all descending):
    1. weighted_severity_score
    2. record_count
    3. avg_confidence

    Parameters
    ----------
    clusters:
        List of ``ErrorCluster`` instances.

    Returns
    -------
    List[ErrorCluster]
        New list sorted by descending impact.
    """
    return sorted(
        clusters,
        key=lambda c: (
            c.metrics["weighted_severity_score"],
            c.metrics["record_count"],
            c.metrics["avg_confidence"],
        ),
        reverse=True,
    )

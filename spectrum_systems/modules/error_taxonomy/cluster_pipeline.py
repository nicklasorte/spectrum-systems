"""
Cluster Pipeline — spectrum_systems/modules/error_taxonomy/cluster_pipeline.py

Orchestrates the full AV → AW0 pipeline:

  1. Load ErrorClassificationRecord objects from AU.
  2. Cluster them deterministically via ErrorClusterer.
  3. Enrich cluster metrics with catalog-derived impact scores.
  4. Rank and filter clusters by impact.
  5. Validate clusters via ClusterValidator (AW0 gate).

Public API
----------
build_clusters_from_classifications(records, catalog, **kwargs) -> List[ErrorCluster]
    Cluster a list of records using default settings.

enrich_clusters_with_catalog(clusters, catalog) -> List[ErrorCluster]
    Re-compute weighted_severity_score using live catalog severity data.
    (In practice the clusterer already embeds this, but this function allows
    re-enrichment after a catalog update.)

rank_and_filter_clusters(clusters, min_size) -> List[ErrorCluster]
    Rank by impact and drop clusters below min_size.

validate_clusters(clusters, classification_records, valid_only) -> List[ValidatedCluster]
    Validate clusters through the AW0 Cluster Validation Layer.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from spectrum_systems.modules.error_taxonomy.clustering import ErrorCluster, ErrorClusterer
from spectrum_systems.modules.error_taxonomy.cluster_validation import (
    ClusterValidator,
    ValidatedCluster,
)
from spectrum_systems.modules.error_taxonomy.impact import rank_clusters

if TYPE_CHECKING:
    from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog
    from spectrum_systems.modules.error_taxonomy.classify import ErrorClassificationRecord


# ---------------------------------------------------------------------------
# Pipeline functions
# ---------------------------------------------------------------------------

def build_clusters_from_classifications(
    classification_records: List["ErrorClassificationRecord"],
    catalog: "ErrorTaxonomyCatalog",
    *,
    min_cluster_size: int = 2,
    severity_weights: Optional[Dict[str, float]] = None,
) -> List[ErrorCluster]:
    """Cluster a list of ErrorClassificationRecord objects.

    Parameters
    ----------
    classification_records:
        Records produced by the AU error taxonomy system.
    catalog:
        Loaded ``ErrorTaxonomyCatalog``.
    min_cluster_size:
        Clusters below this size are merged or kept as singletons.
    severity_weights:
        Optional override for severity weights.

    Returns
    -------
    List[ErrorCluster]
        Ranked clusters (highest impact first).
    """
    clusterer = ErrorClusterer(
        catalog,
        min_cluster_size=min_cluster_size,
        severity_weights=severity_weights,
    )
    clusters = clusterer.group_records(classification_records)
    return rank_clusters(clusters)


def enrich_clusters_with_catalog(
    clusters: List[ErrorCluster],
    catalog: "ErrorTaxonomyCatalog",
    *,
    severity_weights: Optional[Dict[str, float]] = None,
) -> List[ErrorCluster]:
    """Re-compute weighted_severity_score for each cluster using the catalog.

    This is useful when the catalog has been updated and stored clusters need
    their impact scores refreshed without full re-clustering.

    Parameters
    ----------
    clusters:
        List of ``ErrorCluster`` objects.
    catalog:
        Loaded ``ErrorTaxonomyCatalog``.
    severity_weights:
        Optional override for severity weights.

    Returns
    -------
    List[ErrorCluster]
        The same cluster objects with updated ``metrics``.
    """
    from spectrum_systems.modules.error_taxonomy.impact import SEVERITY_WEIGHTS

    _weights = severity_weights or SEVERITY_WEIGHTS

    for cluster in clusters:
        # Re-compute weighted_severity from the signature codes
        sig = cluster.cluster_signature
        all_codes = [sig["primary_error_code"]] + sig["secondary_error_codes"]
        # Use record_count as a proxy weight for each code's contribution
        # (actual per-entry data not stored; use catalog severity × record_count)
        total_weight = 0.0
        for code in set(all_codes):
            subtype = catalog.get_error(code)
            severity = subtype.default_severity if subtype else "medium"
            w = _weights.get(severity, 2.0)
            total_weight += w

        # Scale by record_count and avg_confidence
        enriched_score = (
            total_weight
            * cluster.metrics["record_count"]
            * cluster.metrics["avg_confidence"]
        )
        cluster.metrics["weighted_severity_score"] = round(enriched_score, 4)

    return clusters


def rank_and_filter_clusters(
    clusters: List[ErrorCluster],
    min_size: int = 3,
) -> List[ErrorCluster]:
    """Rank clusters by impact and filter out those below min_size.

    Parameters
    ----------
    clusters:
        List of ``ErrorCluster`` objects.
    min_size:
        Minimum ``record_count`` required to keep a cluster.

    Returns
    -------
    List[ErrorCluster]
        Filtered and ranked cluster list.
    """
    filtered = [c for c in clusters if c.metrics["record_count"] >= min_size]
    return rank_clusters(filtered)


def validate_clusters(
    clusters: List[ErrorCluster],
    classification_records: List["ErrorClassificationRecord"],
    *,
    valid_only: bool = False,
) -> List[ValidatedCluster]:
    """Validate clusters through the AW0 Cluster Validation Layer.

    Parameters
    ----------
    clusters:
        List of ``ErrorCluster`` objects produced by ``build_clusters_from_classifications``.
    classification_records:
        All ``ErrorClassificationRecord`` objects used to build the clusters.
        Used for signature recomputation and per-record confidence checks.
    valid_only:
        If ``True``, return only clusters whose ``validation_status == "valid"``.
        Default: ``False`` (return all validated results).

    Returns
    -------
    List[ValidatedCluster]
        Validated cluster objects in the same order as the input clusters.
    """
    validator = ClusterValidator()

    # Build an index from cluster_id → records for efficient lookup
    record_index: Dict[str, List["ErrorClassificationRecord"]] = {}
    for cluster in clusters:
        # Match records by cluster record_ids if available
        if cluster.record_ids:
            id_set = set(cluster.record_ids)
            record_index[cluster.cluster_id] = [
                r for r in classification_records if r.classification_id in id_set
            ]
        else:
            record_index[cluster.cluster_id] = []

    validated: List[ValidatedCluster] = []
    for cluster in clusters:
        records = record_index.get(cluster.cluster_id, [])
        result = validator.validate_cluster(cluster, records)
        validated.append(result)

    if valid_only:
        return [v for v in validated if v.validation_status == "valid"]
    return validated

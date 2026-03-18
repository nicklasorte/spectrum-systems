"""
Error Taxonomy Module — spectrum_systems/modules/error_taxonomy/__init__.py

Public API exports for the AU Error Taxonomy System and the AV
Auto-Failure Clustering system.
"""
from spectrum_systems.modules.error_taxonomy.catalog import (
    ErrorSubtype,
    ErrorFamily,
    ErrorTaxonomyCatalog,
)
from spectrum_systems.modules.error_taxonomy.classify import (
    ErrorClassificationRecord,
    ErrorClassifier,
)
from spectrum_systems.modules.error_taxonomy.normalize import (
    ClassificationResult,
    normalize_eval_error,
    normalize_feedback_error,
    normalize_observability_error,
    normalize_regression_error,
)
from spectrum_systems.modules.error_taxonomy.bridge import (
    map_legacy_error_type,
    map_failure_type_string,
    infer_from_grounding_failure,
    infer_from_regression_dimension,
)
from spectrum_systems.modules.error_taxonomy.aggregation import (
    count_by_family,
    count_by_subtype,
    count_by_remediation_target,
    count_by_source_system,
    count_by_pass_type,
    identify_highest_impact_subtypes,
)
from spectrum_systems.modules.error_taxonomy.clustering import (
    ErrorCluster,
    ErrorClusterer,
)
from spectrum_systems.modules.error_taxonomy.impact import (
    SEVERITY_WEIGHTS,
    compute_weighted_severity,
    compute_cluster_impact,
    rank_clusters,
)
from spectrum_systems.modules.error_taxonomy.cluster_store import (
    save_cluster,
    load_cluster,
    list_clusters,
)
from spectrum_systems.modules.error_taxonomy.cluster_pipeline import (
    build_clusters_from_classifications,
    enrich_clusters_with_catalog,
    rank_and_filter_clusters,
)

__all__ = [
    # catalog
    "ErrorSubtype",
    "ErrorFamily",
    "ErrorTaxonomyCatalog",
    # classify
    "ErrorClassificationRecord",
    "ErrorClassifier",
    # normalize
    "ClassificationResult",
    "normalize_eval_error",
    "normalize_feedback_error",
    "normalize_observability_error",
    "normalize_regression_error",
    # bridge
    "map_legacy_error_type",
    "map_failure_type_string",
    "infer_from_grounding_failure",
    "infer_from_regression_dimension",
    # aggregation
    "count_by_family",
    "count_by_subtype",
    "count_by_remediation_target",
    "count_by_source_system",
    "count_by_pass_type",
    "identify_highest_impact_subtypes",
    # clustering (AV)
    "ErrorCluster",
    "ErrorClusterer",
    # impact (AV)
    "SEVERITY_WEIGHTS",
    "compute_weighted_severity",
    "compute_cluster_impact",
    "rank_clusters",
    # cluster store (AV)
    "save_cluster",
    "load_cluster",
    "list_clusters",
    # cluster pipeline (AV)
    "build_clusters_from_classifications",
    "enrich_clusters_with_catalog",
    "rank_and_filter_clusters",
]

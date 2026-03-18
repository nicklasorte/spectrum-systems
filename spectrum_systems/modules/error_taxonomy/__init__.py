"""
Error Taxonomy Module — spectrum_systems/modules/error_taxonomy/__init__.py

Public API exports for the AU Error Taxonomy System.
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
]

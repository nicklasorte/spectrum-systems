"""
Backward Compatibility Bridge — spectrum_systems/modules/error_taxonomy/bridge.py

Maps existing coarse ``ErrorType`` enum values from AN/AP/AO modules into the
richer AU canonical taxonomy codes, without breaking existing callers.

Design principles
-----------------
- Existing systems keep working; existing ErrorType usage is unchanged.
- This module is a one-way bridge: old → new.
- Mapping is deterministic and explicit.
- Partial evidence produces multi-code outputs with reduced confidence.

Public API
----------
map_legacy_error_type(error_type) -> List[str]
    Map an ``ErrorType`` enum value to canonical taxonomy codes.

map_failure_type_string(failure_type_str) -> List[str]
    Map a failure_type string to canonical taxonomy codes.

infer_from_grounding_failure(missing_refs, mismatched_refs, declared_refs) -> List[str]
    Infer grounding/hallucination codes from reference signals.

infer_from_regression_dimension(dimension, severity) -> str
    Infer a REGRESS.* code from a regression dimension name.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Import the legacy ErrorType to avoid circular dependencies
from spectrum_systems.modules.evaluation.error_taxonomy import ErrorType


# ---------------------------------------------------------------------------
# Legacy ErrorType → canonical taxonomy codes
# ---------------------------------------------------------------------------

# Primary mapping: each legacy ErrorType maps to a list of canonical codes.
# First entry is the highest-confidence primary code.
_ERROR_TYPE_PRIMARY_MAP: Dict[str, List[str]] = {
    ErrorType.extraction_error.value: ["EXTRACT.MISSED_DECISION"],
    ErrorType.reasoning_error.value: ["REASON.BAD_INFERENCE"],
    ErrorType.grounding_failure.value: ["GROUND.MISSING_REF"],
    ErrorType.schema_violation.value: ["SCHEMA.INVALID_OUTPUT"],
    ErrorType.hallucination.value: ["HALLUC.UNSUPPORTED_ASSERTION"],
    ErrorType.regression_failure.value: ["REGRESS.STRUCTURAL_DROP"],
}

# Failure type strings that appear in feedback records and observability
_FAILURE_TYPE_PRIMARY_MAP: Dict[str, List[str]] = {
    "extraction_error": ["EXTRACT.MISSED_DECISION"],
    "reasoning_error": ["REASON.BAD_INFERENCE"],
    "grounding_failure": ["GROUND.MISSING_REF"],
    "schema_violation": ["SCHEMA.INVALID_OUTPUT"],
    "hallucination": ["HALLUC.UNSUPPORTED_ASSERTION"],
    "regression_failure": ["REGRESS.STRUCTURAL_DROP"],
    "unclear": ["EXTRACT.MISSED_DECISION"],  # weakest fallback
}


def map_legacy_error_type(error_type: Any) -> List[str]:
    """Map an ``ErrorType`` enum value to canonical AU taxonomy codes.

    Parameters
    ----------
    error_type:
        An ``ErrorType`` enum value or its string equivalent.

    Returns
    -------
    List[str]
        List of canonical error codes (primary first).  Never empty.
    """
    value = error_type.value if isinstance(error_type, ErrorType) else str(error_type)
    return list(_ERROR_TYPE_PRIMARY_MAP.get(value, ["EXTRACT.MISSED_DECISION"]))


def map_failure_type_string(failure_type_str: str) -> List[str]:
    """Map a failure_type string to canonical AU taxonomy codes.

    Parameters
    ----------
    failure_type_str:
        String value from ``HumanFeedbackRecord.failure_type`` or similar.

    Returns
    -------
    List[str]
        List of canonical error codes.  Never empty.
    """
    return list(_FAILURE_TYPE_PRIMARY_MAP.get(failure_type_str, ["EXTRACT.MISSED_DECISION"]))


def infer_from_grounding_failure(
    missing_refs: List[str],
    mismatched_refs: List[str],
    declared_refs: Optional[List[str]] = None,
) -> List[str]:
    """Infer grounding or hallucination codes from reference failure signals.

    Parameters
    ----------
    missing_refs:
        References that could not be resolved.
    mismatched_refs:
        References that exist but do not match the claim.
    declared_refs:
        All declared upstream references for the claim.

    Returns
    -------
    List[str]
        One or more canonical GROUND.* or HALLUC.* codes.
    """
    codes: List[str] = []
    declared_refs = declared_refs or []

    if not missing_refs and not mismatched_refs:
        return ["GROUND.MISSING_REF"]  # fallback if called with empty lists

    # Hallucination: all declared refs are missing and no mismatches (nothing to mismatch)
    all_missing = (
        bool(missing_refs)
        and bool(declared_refs)
        and len(missing_refs) >= len(declared_refs)
        and not mismatched_refs
    )

    if all_missing:
        codes.append("HALLUC.UNSUPPORTED_ASSERTION")
    else:
        if missing_refs:
            codes.append("GROUND.MISSING_REF")
        if mismatched_refs:
            codes.append("GROUND.WEAK_SUPPORT")

    return codes


def infer_from_regression_dimension(dimension: str, severity: str = "warning") -> str:
    """Infer a canonical REGRESS.* or related code from a regression dimension.

    Parameters
    ----------
    dimension:
        Regression dimension name (e.g. ``"grounding_score"``).
    severity:
        Gate severity: ``"hard_fail"`` | ``"warning"`` | ``"info"``.

    Returns
    -------
    str
        Canonical error code.
    """
    _DIM_MAP: Dict[str, str] = {
        "grounding_score": "REGRESS.GROUNDING_DROP",
        "structural_score": "REGRESS.STRUCTURAL_DROP",
        "semantic_score": "REGRESS.SEMANTIC_DROP",
        "latency": "REGRESS.LATENCY_SPIKE",
        "latency_ms": "REGRESS.LATENCY_SPIKE",
        "human_disagreement": "HUMAN.REVIEWER_DISAGREEMENT",
    }
    return _DIM_MAP.get(dimension, "REGRESS.STRUCTURAL_DROP")

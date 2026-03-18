"""
Error Taxonomy — spectrum_systems/modules/evaluation/error_taxonomy.py

Classifies evaluation failures into typed error categories.

Every failure in the evaluation pipeline must be tagged with an
``ErrorType``.  This module provides the canonical taxonomy and helpers for
classifying errors from raw failure data.

Design principles
-----------------
- All failure types are explicit: no catch-all ``"unknown"`` in production paths.
- Classification is deterministic given the same inputs.
- No external dependencies beyond the Python standard library.

Public API
----------
ErrorType
    Enumeration of all recognised error types.

EvalError
    A single classified evaluation error.

classify_error(failure_info) -> EvalError
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

class ErrorType(str, Enum):
    """Canonical taxonomy of evaluation error types.

    Values
    ------
    extraction_error
        A pass failed to extract expected structured data from input.
    reasoning_error
        A reasoning-class pass produced an incorrect or internally
        inconsistent conclusion.
    grounding_failure
        A synthesized claim lacks a traceable upstream reference, or the
        reference does not semantically match the claim.
    schema_violation
        A pass output failed JSON schema validation.
    hallucination
        A synthesized output contains content with no basis in the input
        artifacts (severe grounding failure with zero upstream evidence).
    regression_failure
        A current evaluation run produces scores below the stored baseline
        beyond the configured threshold.
"""

    extraction_error = "extraction_error"
    reasoning_error = "reasoning_error"
    grounding_failure = "grounding_failure"
    schema_violation = "schema_violation"
    hallucination = "hallucination"
    regression_failure = "regression_failure"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EvalError:
    """A single classified evaluation error.

    Attributes
    ----------
    error_type:
        Classified ``ErrorType``.
    message:
        Human-readable description of the error.
    pass_id:
        Identifier of the pass that produced this error, if applicable.
    details:
        Additional structured detail dict (e.g., schema validation errors,
        missing references).
    """

    error_type: ErrorType
    message: str
    pass_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Classification helper
# ---------------------------------------------------------------------------

def classify_error(failure_info: Dict[str, Any]) -> EvalError:
    """Classify a raw failure dict into a typed ``EvalError``.

    Classification rules (checked in order):

    1. ``"schema_errors"`` present and non-empty → ``schema_violation``
    2. ``"missing_refs"`` or ``"mismatched_refs"`` present → grounding or
       hallucination (hallucination if ``missing_refs`` covers ALL declared
       refs, i.e., no valid upstream evidence at all).
    3. ``"pass_type"`` is a reasoning-class type → ``reasoning_error``
    4. ``"pass_type"`` is an extraction type → ``extraction_error``
    5. ``"regression"`` key present → ``regression_failure``
    6. Fallback: ``extraction_error``

    Parameters
    ----------
    failure_info:
        Dict describing the failure.  Recognised keys:

        - ``"pass_type"`` (str) — type of the failing pass
        - ``"schema_errors"`` (list[str]) — schema validation errors
        - ``"missing_refs"`` (list[str]) — unresolvable upstream refs
        - ``"mismatched_refs"`` (list[str]) — semantically inconsistent refs
        - ``"upstream_pass_refs"`` (list[str]) — all declared refs for the claim
        - ``"regression"`` (bool) — whether this is a regression failure
        - ``"message"`` (str) — optional human-readable description
        - ``"pass_id"`` (str) — optional pass identifier

    Returns
    -------
    EvalError
    """
    pass_id: Optional[str] = failure_info.get("pass_id")
    message: str = failure_info.get("message", "Unclassified evaluation failure")
    pass_type: str = failure_info.get("pass_type", "")
    schema_errors: List[str] = failure_info.get("schema_errors", [])
    missing_refs: List[str] = failure_info.get("missing_refs", [])
    mismatched_refs: List[str] = failure_info.get("mismatched_refs", [])
    declared_refs: List[str] = failure_info.get("upstream_pass_refs", [])
    is_regression: bool = bool(failure_info.get("regression", False))

    # 1. Schema violation
    if schema_errors:
        return EvalError(
            error_type=ErrorType.schema_violation,
            message=message or f"Schema validation failed: {schema_errors[0]}",
            pass_id=pass_id,
            details={"schema_errors": schema_errors},
        )

    # 2. Grounding / hallucination
    if missing_refs or mismatched_refs:
        # Hallucination: ALL declared refs are missing (no upstream evidence)
        is_hallucination = (
            bool(missing_refs)
            and len(missing_refs) == len(declared_refs)
            and not mismatched_refs
        )
        error_type = ErrorType.hallucination if is_hallucination else ErrorType.grounding_failure
        return EvalError(
            error_type=error_type,
            message=message or (
                f"Claim has no upstream evidence (hallucination)"
                if is_hallucination
                else f"Grounding failure: missing={missing_refs}, mismatched={mismatched_refs}"
            ),
            pass_id=pass_id,
            details={
                "missing_refs": missing_refs,
                "mismatched_refs": mismatched_refs,
            },
        )

    # 3. Reasoning error
    _REASONING_TYPES = {
        "decision_extraction", "contradiction_detection",
        "gap_detection", "adversarial_review",
    }
    if pass_type in _REASONING_TYPES:
        return EvalError(
            error_type=ErrorType.reasoning_error,
            message=message or f"Reasoning pass '{pass_type}' produced an incorrect output",
            pass_id=pass_id,
            details=failure_info,
        )

    # 4. Regression failure
    if is_regression:
        return EvalError(
            error_type=ErrorType.regression_failure,
            message=message or "Score regression detected against stored baseline",
            pass_id=pass_id,
            details=failure_info,
        )

    # 5. Extraction error (default for extraction passes and fallback)
    return EvalError(
        error_type=ErrorType.extraction_error,
        message=message or f"Extraction failure in pass '{pass_type}'",
        pass_id=pass_id,
        details=failure_info,
    )

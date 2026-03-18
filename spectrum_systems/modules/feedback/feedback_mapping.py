"""
Feedback → Error Taxonomy Bridge — spectrum_systems/modules/feedback/feedback_mapping.py

Maps human feedback records to ``ErrorType`` values from the AU error taxonomy,
enabling feedback data to flow directly into the evaluation pipeline.

Design principles
-----------------
- Mapping is deterministic and explicit; no heuristics.
- The ``failure_type`` field in ``HumanFeedbackRecord`` is intentionally
  designed to align with ``ErrorType`` values so mapping is trivial.
- When a feedback record carries ``failure_type="unclear"``, the mapper falls
  back to ``action``-based inference.

Public API
----------
map_feedback_to_error_type(feedback_record) -> ErrorType
    Return the matching ``ErrorType`` for a feedback record.
"""
from __future__ import annotations

from spectrum_systems.modules.evaluation.error_taxonomy import ErrorType
from spectrum_systems.modules.feedback.human_feedback import HumanFeedbackRecord


# ---------------------------------------------------------------------------
# Explicit failure_type → ErrorType mapping
# ---------------------------------------------------------------------------

_FAILURE_TYPE_MAP: dict = {
    "extraction_error": ErrorType.extraction_error,
    "reasoning_error": ErrorType.reasoning_error,
    "grounding_failure": ErrorType.grounding_failure,
    "hallucination": ErrorType.hallucination,
    "schema_violation": ErrorType.schema_violation,
}

# ---------------------------------------------------------------------------
# Action → ErrorType fallback (used when failure_type == "unclear")
# ---------------------------------------------------------------------------

_ACTION_FALLBACK_MAP: dict = {
    "reject": ErrorType.reasoning_error,
    "rewrite": ErrorType.reasoning_error,
    "major_edit": ErrorType.extraction_error,
    "minor_edit": ErrorType.extraction_error,
    "needs_support": ErrorType.grounding_failure,
    "accept": ErrorType.extraction_error,  # accepted = no real error; use least severe
}


def map_feedback_to_error_type(feedback_record: HumanFeedbackRecord) -> ErrorType:
    """Return the ``ErrorType`` that best represents the feedback record.

    Mapping rules (checked in order):

    1. If ``failure_type`` is a direct match in the taxonomy, return it.
    2. If ``failure_type == "unclear"``, infer from ``action``.
    3. Fallback: ``ErrorType.extraction_error``.

    Parameters
    ----------
    feedback_record:
        ``HumanFeedbackRecord`` to map.

    Returns
    -------
    ErrorType
        The matched ``ErrorType``.
    """
    failure_type = feedback_record.failure_type

    if failure_type in _FAILURE_TYPE_MAP:
        return _FAILURE_TYPE_MAP[failure_type]

    # "unclear" — use action-based fallback
    return _ACTION_FALLBACK_MAP.get(feedback_record.action, ErrorType.extraction_error)

"""
Normalization Layer — spectrum_systems/modules/error_taxonomy/normalize.py

Maps coarse signals from evaluation, feedback, observability, and regression
into canonical AU taxonomy error codes.

Design principles
-----------------
- Output is always one or more canonical error codes.
- Partial confidence is surfaced explicitly rather than hidden.
- Raw source signals are never discarded.
- Multi-label classification is supported where evidence warrants it.
- No generic catch-all unless evidence is truly insufficient.

Public API
----------
ClassificationResult
    A single canonical error code classification with confidence metadata.

normalize_eval_error(failure_info) -> List[ClassificationResult]
normalize_feedback_error(feedback_dict) -> List[ClassificationResult]
normalize_observability_error(obs_dict) -> List[ClassificationResult]
normalize_regression_error(regression_entry) -> List[ClassificationResult]
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    """A single canonical taxonomy classification.

    Attributes
    ----------
    error_code:
        Canonical taxonomy code (e.g. ``GROUND.MISSING_REF``).
    confidence:
        Confidence in this classification (0.0–1.0).
    evidence_source:
        Which field or signal from the raw input supports this classification.
    explanation:
        Human-readable explanation for the assignment.
    """

    error_code: str
    confidence: float
    evidence_source: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "confidence": self.confidence,
            "evidence_source": self.evidence_source,
            "explanation": self.explanation,
        }


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

# Evaluation pass types associated with reasoning errors
_REASONING_PASS_TYPES = frozenset({
    "decision_extraction",
    "contradiction_detection",
    "gap_detection",
    "adversarial_review",
})

# Evaluation pass types associated with extraction errors
_EXTRACTION_PASS_TYPES = frozenset({
    "action_item_extraction",
    "extraction",
    "summary_extraction",
})


def normalize_eval_error(failure_info: Dict[str, Any]) -> List[ClassificationResult]:
    """Normalize an evaluation failure dict into canonical taxonomy codes.

    Parameters
    ----------
    failure_info:
        Dict describing the evaluation failure.  Recognised keys:

        - ``"pass_type"`` (str)
        - ``"schema_errors"`` (list[str])
        - ``"missing_refs"`` (list[str])
        - ``"mismatched_refs"`` (list[str])
        - ``"upstream_pass_refs"`` (list[str])
        - ``"regression"`` (bool)
        - ``"message"`` (str)
        - ``"pass_id"`` (str)

    Returns
    -------
    List[ClassificationResult]
        One or more canonical classifications.
    """
    results: List[ClassificationResult] = []

    pass_type: str = failure_info.get("pass_type", "")
    schema_errors: List[str] = failure_info.get("schema_errors", [])
    missing_refs: List[str] = failure_info.get("missing_refs", [])
    mismatched_refs: List[str] = failure_info.get("mismatched_refs", [])
    declared_refs: List[str] = failure_info.get("upstream_pass_refs", [])
    is_regression: bool = bool(failure_info.get("regression", False))
    message: str = failure_info.get("message", "")

    # Schema errors
    if schema_errors:
        first_err = schema_errors[0].upper()
        code = "SCHEMA.INVALID_OUTPUT" if "JSON" in first_err else "SCHEMA.MISSING_REQUIRED_FIELD"
        results.append(ClassificationResult(
            error_code=code,
            confidence=0.95,
            evidence_source="schema_errors",
            explanation=f"Schema validation failed: {schema_errors[0]}",
        ))
        # Type mismatch is a secondary classification when type-related errors present
        if any("type" in e.lower() for e in schema_errors):
            results.append(ClassificationResult(
                error_code="SCHEMA.TYPE_MISMATCH",
                confidence=0.75,
                evidence_source="schema_errors",
                explanation="Schema error indicates type mismatch.",
            ))

    # Grounding / hallucination
    if missing_refs or mismatched_refs:
        all_missing = (
            bool(missing_refs)
            and declared_refs
            and len(missing_refs) >= len(declared_refs)
            and not mismatched_refs
        )
        if all_missing:
            results.append(ClassificationResult(
                error_code="HALLUC.UNSUPPORTED_ASSERTION",
                confidence=0.90,
                evidence_source="missing_refs",
                explanation=(
                    f"All {len(missing_refs)} declared refs are missing; "
                    "claim has no upstream evidence."
                ),
            ))
        else:
            if missing_refs:
                results.append(ClassificationResult(
                    error_code="GROUND.MISSING_REF",
                    confidence=0.90,
                    evidence_source="missing_refs",
                    explanation=f"{len(missing_refs)} reference(s) could not be resolved.",
                ))
            if mismatched_refs:
                results.append(ClassificationResult(
                    error_code="GROUND.WEAK_SUPPORT",
                    confidence=0.75,
                    evidence_source="mismatched_refs",
                    explanation=f"{len(mismatched_refs)} reference(s) do not semantically match the claim.",
                ))

    # Reasoning pass type
    if pass_type in _REASONING_PASS_TYPES and not results:
        code = "REASON.CONTRADICTION_MISSED" if pass_type == "contradiction_detection" else \
               "REASON.GAP_MISSED" if pass_type == "gap_detection" else \
               "REASON.BAD_INFERENCE"
        results.append(ClassificationResult(
            error_code=code,
            confidence=0.70,
            evidence_source="pass_type",
            explanation=f"Reasoning pass '{pass_type}' failed.",
        ))

    # Extraction pass type
    if pass_type in _EXTRACTION_PASS_TYPES and not results:
        code = "EXTRACT.MISSED_ACTION_ITEM" if pass_type == "action_item_extraction" else \
               "EXTRACT.MISSED_DECISION"
        results.append(ClassificationResult(
            error_code=code,
            confidence=0.65,
            evidence_source="pass_type",
            explanation=f"Extraction pass '{pass_type}' failed.",
        ))

    # Regression
    if is_regression:
        if not any(r.error_code.startswith("REGRESS.") for r in results):
            results.append(ClassificationResult(
                error_code="REGRESS.STRUCTURAL_DROP",
                confidence=0.60,
                evidence_source="regression",
                explanation="Regression flag set in evaluation failure.",
            ))

    # Fallback
    if not results:
        code = "REASON.BAD_INFERENCE" if pass_type in _REASONING_PASS_TYPES else "EXTRACT.FALSE_EXTRACTION"
        results.append(ClassificationResult(
            error_code=code,
            confidence=0.40,
            evidence_source="message",
            explanation=message or "Unclassified evaluation failure; low-confidence fallback.",
        ))

    return results


def normalize_feedback_error(feedback_dict: Dict[str, Any]) -> List[ClassificationResult]:
    """Normalize a human feedback record dict into canonical taxonomy codes.

    Parameters
    ----------
    feedback_dict:
        Dict from a ``HumanFeedbackRecord``.  Recognised keys:

        - ``"failure_type"`` (str)
        - ``"action"`` (str)
        - ``"source_of_truth"`` (str)
        - ``"rationale"`` (str)
        - ``"severity"`` (str)

    Returns
    -------
    List[ClassificationResult]
    """
    results: List[ClassificationResult] = []

    failure_type: str = feedback_dict.get("failure_type", "")
    action: str = feedback_dict.get("action", "")
    rationale: str = feedback_dict.get("rationale", "")
    severity: str = feedback_dict.get("severity", "")

    # Explicit failure type → taxonomy code mapping
    _FAILURE_TYPE_MAP: Dict[str, str] = {
        "extraction_error": "EXTRACT.MISSED_DECISION",
        "reasoning_error": "REASON.BAD_INFERENCE",
        "grounding_failure": "GROUND.MISSING_REF",
        "hallucination": "HALLUC.UNSUPPORTED_ASSERTION",
        "schema_violation": "SCHEMA.INVALID_OUTPUT",
        "regression_failure": "REGRESS.STRUCTURAL_DROP",
    }

    if failure_type in _FAILURE_TYPE_MAP:
        results.append(ClassificationResult(
            error_code=_FAILURE_TYPE_MAP[failure_type],
            confidence=0.85,
            evidence_source="failure_type",
            explanation=f"Feedback failure_type='{failure_type}' maps to this code.",
        ))

    # Action → additional taxonomy signals
    if action == "needs_support":
        results.append(ClassificationResult(
            error_code="HUMAN.NEEDS_SUPPORT",
            confidence=0.95,
            evidence_source="action",
            explanation="Reviewer action 'needs_support' directly maps to HUMAN.NEEDS_SUPPORT.",
        ))
        # needs_support almost always co-occurs with grounding weakness
        if not any(r.error_code.startswith("GROUND.") for r in results):
            results.append(ClassificationResult(
                error_code="GROUND.WEAK_SUPPORT",
                confidence=0.70,
                evidence_source="action",
                explanation="'needs_support' action typically indicates weak grounding.",
            ))

    elif action in ("rewrite",):
        results.append(ClassificationResult(
            error_code="HUMAN.REWRITE_REQUIRED",
            confidence=0.95,
            evidence_source="action",
            explanation="Reviewer action 'rewrite' maps to HUMAN.REWRITE_REQUIRED.",
        ))

    elif action == "reject":
        if not results:
            results.append(ClassificationResult(
                error_code="HUMAN.REVIEWER_DISAGREEMENT",
                confidence=0.85,
                evidence_source="action",
                explanation="Reviewer 'reject' action indicates disagreement.",
            ))

    # Severity escalation
    if severity == "critical" and results:
        # Promote first result to a stronger code if applicable
        pass  # severity is captured in the raw signal; no code promotion needed

    # Fallback
    if not results:
        results.append(ClassificationResult(
            error_code="HUMAN.REVIEWER_DISAGREEMENT",
            confidence=0.40,
            evidence_source="action",
            explanation=f"Feedback action='{action}' with unclear failure_type; low-confidence fallback.",
        ))

    return results


def normalize_observability_error(obs_dict: Dict[str, Any]) -> List[ClassificationResult]:
    """Normalize an observability record dict into canonical taxonomy codes.

    Parameters
    ----------
    obs_dict:
        Dict from an ``ObservabilityRecord``.  Recognised keys:

        - ``"error_types"`` (list[str])
        - ``"flags"`` (dict with schema_valid, grounding_passed, etc.)
        - ``"scores"`` (dict)
        - ``"pass_type"`` (str)
        - ``"failure_count"`` (int)

    Returns
    -------
    List[ClassificationResult]
    """
    results: List[ClassificationResult] = []

    flags = obs_dict.get("flags", {})
    error_types: List[str] = obs_dict.get("error_types", [])
    scores = obs_dict.get("scores", {})
    pass_type: str = obs_dict.get("pass_type", "")

    # Schema failures
    if not flags.get("schema_valid", True):
        results.append(ClassificationResult(
            error_code="SCHEMA.INVALID_OUTPUT",
            confidence=0.90,
            evidence_source="flags.schema_valid",
            explanation="Observability flag schema_valid=false.",
        ))

    # Grounding failures
    if not flags.get("grounding_passed", True):
        grounding_score = scores.get("grounding_score", None)
        if grounding_score is not None and grounding_score == 0.0:
            results.append(ClassificationResult(
                error_code="HALLUC.UNSUPPORTED_ASSERTION",
                confidence=0.85,
                evidence_source="flags.grounding_passed + scores.grounding_score",
                explanation=f"Grounding passed=false and grounding_score=0.0 indicates no valid references.",
            ))
        else:
            results.append(ClassificationResult(
                error_code="GROUND.MISSING_REF",
                confidence=0.80,
                evidence_source="flags.grounding_passed",
                explanation="Observability flag grounding_passed=false.",
            ))

    # Regression flags
    if not flags.get("regression_passed", True):
        results.append(ClassificationResult(
            error_code="REGRESS.STRUCTURAL_DROP",
            confidence=0.75,
            evidence_source="flags.regression_passed",
            explanation="Observability flag regression_passed=false.",
        ))

    # Human disagreement
    if flags.get("human_disagrees", False):
        results.append(ClassificationResult(
            error_code="HUMAN.REVIEWER_DISAGREEMENT",
            confidence=0.85,
            evidence_source="flags.human_disagrees",
            explanation="Observability flag human_disagrees=true.",
        ))

    # Error types from the legacy taxonomy
    _OBS_ERROR_TYPE_MAP: Dict[str, str] = {
        "extraction_error": "EXTRACT.MISSED_DECISION",
        "reasoning_error": "REASON.BAD_INFERENCE",
        "grounding_failure": "GROUND.MISSING_REF",
        "hallucination": "HALLUC.UNSUPPORTED_ASSERTION",
        "schema_violation": "SCHEMA.INVALID_OUTPUT",
        "regression_failure": "REGRESS.STRUCTURAL_DROP",
    }
    for et in error_types:
        code = _OBS_ERROR_TYPE_MAP.get(et)
        if code and not any(r.error_code == code for r in results):
            results.append(ClassificationResult(
                error_code=code,
                confidence=0.70,
                evidence_source="error_types",
                explanation=f"Observability error_type='{et}' mapped to {code}.",
            ))

    # Score-based classifications (low confidence — metric signals)
    structural = scores.get("structural_score")
    semantic = scores.get("semantic_score")
    grounding = scores.get("grounding_score")

    if structural is not None and structural < 0.5:
        if not any(r.error_code == "REGRESS.STRUCTURAL_DROP" for r in results):
            results.append(ClassificationResult(
                error_code="REGRESS.STRUCTURAL_DROP",
                confidence=0.55,
                evidence_source="scores.structural_score",
                explanation=f"Low structural_score={structural:.2f} suggests structural degradation.",
            ))

    if grounding is not None and grounding < 0.5:
        if not any(r.error_code.startswith("GROUND.") or r.error_code.startswith("HALLUC.") for r in results):
            results.append(ClassificationResult(
                error_code="GROUND.WEAK_SUPPORT",
                confidence=0.55,
                evidence_source="scores.grounding_score",
                explanation=f"Low grounding_score={grounding:.2f} suggests weak grounding.",
            ))

    # Fallback
    if not results:
        results.append(ClassificationResult(
            error_code="EXTRACT.FALSE_EXTRACTION",
            confidence=0.30,
            evidence_source="observability_record",
            explanation="No specific error signals found; low-confidence fallback.",
        ))

    return results


def normalize_regression_error(regression_entry: Dict[str, Any]) -> List[ClassificationResult]:
    """Normalize a regression report entry into canonical taxonomy codes.

    Parameters
    ----------
    regression_entry:
        A ``worst_regressions`` entry dict from a ``RegressionReport``.
        Recognised keys:

        - ``"dimension"`` (str) — e.g. ``"grounding_score"``
        - ``"delta"`` (float) — negative means regression
        - ``"severity"`` (str) — ``"hard_fail"`` | ``"warning"`` | ``"info"``
        - ``"explanation"`` (str)
        - ``"pass_id"`` (str, optional)

    Returns
    -------
    List[ClassificationResult]
    """
    results: List[ClassificationResult] = []

    dimension: str = regression_entry.get("dimension", "")
    delta: float = regression_entry.get("delta", 0.0)
    severity: str = regression_entry.get("severity", "warning")
    explanation: str = regression_entry.get("explanation", "")

    _DIMENSION_CODE_MAP: Dict[str, str] = {
        "grounding_score": "REGRESS.GROUNDING_DROP",
        "structural_score": "REGRESS.STRUCTURAL_DROP",
        "semantic_score": "REGRESS.SEMANTIC_DROP",
        "latency": "REGRESS.LATENCY_SPIKE",
        "latency_ms": "REGRESS.LATENCY_SPIKE",
        "human_disagreement": "HUMAN.REVIEWER_DISAGREEMENT",
    }

    code = _DIMENSION_CODE_MAP.get(dimension)
    if code:
        confidence = 0.90 if severity == "hard_fail" else 0.75
        results.append(ClassificationResult(
            error_code=code,
            confidence=confidence,
            evidence_source=f"dimension={dimension}",
            explanation=explanation or f"Regression detected in dimension '{dimension}' (delta={delta:.3f}).",
        ))
    else:
        # Unknown dimension — partial confidence
        results.append(ClassificationResult(
            error_code="REGRESS.STRUCTURAL_DROP",
            confidence=0.40,
            evidence_source=f"dimension={dimension}",
            explanation=f"Unknown regression dimension '{dimension}'; mapped to REGRESS.STRUCTURAL_DROP with low confidence.",
        ))

    return results

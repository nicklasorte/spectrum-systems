"""
TLC Router — spectrum_systems/modules/orchestration/tlc_router.py

TLC is the sole orchestration authority. This module enforces routing rules for
the transcript-to-study pipeline. All artifact-type transitions are explicit,
enumerated, and fail-closed.

Routing table (transcript pipeline):
  transcript_artifact      → context_bundle
  context_bundle           → meeting_minutes_artifact
  meeting_minutes_artifact → issue_registry_artifact
  issue_registry_artifact  → structured_issue_set
  structured_issue_set     → paper_draft_artifact
  paper_draft_artifact     → review_artifact
  review_artifact          → revised_draft_artifact
  revised_draft_artifact   → formatted_paper_artifact
  formatted_paper_artifact → release_artifact
  release_artifact         → [terminal]

Rules:
- Missing route → FAIL (ArtifactRoutingError)
- Circular routes are statically detected at module load
- No implicit fallback routing
- route_artifact() is the sole routing interface
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

_PIPELINE_ROUTES: Dict[str, str] = {
    "transcript_artifact": "context_bundle",
    "context_bundle": "meeting_minutes_artifact",
    "meeting_minutes_artifact": "issue_registry_artifact",
    "issue_registry_artifact": "structured_issue_set",
    "structured_issue_set": "paper_draft_artifact",
    "paper_draft_artifact": "review_artifact",
    "review_artifact": "revised_draft_artifact",
    "revised_draft_artifact": "formatted_paper_artifact",
    "formatted_paper_artifact": "release_artifact",
}

_TERMINAL_TYPES = frozenset(["release_artifact"])

_PIPELINE_ORDER: List[str] = [
    "transcript_artifact",
    "context_bundle",
    "meeting_minutes_artifact",
    "issue_registry_artifact",
    "structured_issue_set",
    "paper_draft_artifact",
    "review_artifact",
    "revised_draft_artifact",
    "formatted_paper_artifact",
    "release_artifact",
]


class ArtifactRoutingError(RuntimeError):
    """Raised when a routing rule is violated. Always carries reason_codes."""

    def __init__(self, message: str, reason_codes: List[str], artifact_type: Optional[str] = None) -> None:
        super().__init__(message)
        self.reason_codes = reason_codes
        self.artifact_type = artifact_type

    def to_dict(self) -> Dict[str, object]:
        return {
            "error": str(self),
            "reason_codes": self.reason_codes,
            "artifact_type": self.artifact_type,
        }


def _detect_cycles(routes: Dict[str, str]) -> List[List[str]]:
    """Return all cycles found in the routing table."""
    cycles: List[List[str]] = []
    visited: Dict[str, int] = {}

    for start in routes:
        path: List[str] = []
        current = start
        seen_in_path: set = set()

        while current in routes:
            if current in seen_in_path:
                cycle_start = path.index(current)
                cycles.append(path[cycle_start:])
                break
            if current in visited:
                break
            seen_in_path.add(current)
            path.append(current)
            current = routes[current]

        for node in path:
            visited[node] = 1

    return cycles


_STARTUP_CYCLES = _detect_cycles(_PIPELINE_ROUTES)
if _STARTUP_CYCLES:
    raise RuntimeError(
        f"FATAL: TLC routing table contains cycles at module load: {_STARTUP_CYCLES}. "
        "This is a hard invariant violation."
    )


def route_artifact(artifact_type: str) -> str:
    """Return the next artifact type for a given input artifact type.

    Raises ArtifactRoutingError for unknown or terminal artifact types.
    Raises ArtifactRoutingError if artifact_type is missing or invalid.

    CALLER RESPONSIBILITY: This function performs type-based routing only.
    It does NOT verify that eval gates have passed for the artifact before routing.
    The TLC caller MUST enforce eval gates (via enforce_eval_gate) before calling
    route_artifact. Routing an artifact that has not passed eval gates violates
    the eval-before-trust invariant.
    """
    if not artifact_type or not isinstance(artifact_type, str):
        raise ArtifactRoutingError(
            "artifact_type must be a non-empty string",
            reason_codes=["INVALID_ARTIFACT_TYPE"],
            artifact_type=str(artifact_type) if artifact_type else None,
        )

    if artifact_type in _TERMINAL_TYPES:
        raise ArtifactRoutingError(
            f"Artifact type '{artifact_type}' is a terminal state — no further routing.",
            reason_codes=["TERMINAL_ARTIFACT_TYPE"],
            artifact_type=artifact_type,
        )

    next_type = _PIPELINE_ROUTES.get(artifact_type)
    if next_type is None:
        raise ArtifactRoutingError(
            f"No routing rule defined for artifact_type='{artifact_type}'. "
            f"Known types: {sorted(_PIPELINE_ROUTES.keys())}",
            reason_codes=["NO_ROUTE_DEFINED"],
            artifact_type=artifact_type,
        )

    return next_type


def is_terminal(artifact_type: str) -> bool:
    """Return True if the artifact type is a terminal (end-of-pipeline) state."""
    return artifact_type in _TERMINAL_TYPES


def pipeline_position(artifact_type: str) -> int:
    """Return the 0-based position of an artifact type in the pipeline order.

    Raises ArtifactRoutingError if the type is unknown.
    """
    try:
        return _PIPELINE_ORDER.index(artifact_type)
    except ValueError:
        raise ArtifactRoutingError(
            f"artifact_type='{artifact_type}' is not in the pipeline order",
            reason_codes=["UNKNOWN_PIPELINE_POSITION"],
            artifact_type=artifact_type,
        )


def validate_transition(from_type: str, to_type: str) -> None:
    """Assert that transitioning from from_type to to_type is valid.

    Raises ArtifactRoutingError if the transition violates routing rules.
    """
    expected_next = route_artifact(from_type)
    if to_type != expected_next:
        raise ArtifactRoutingError(
            f"Invalid transition: '{from_type}' → '{to_type}'. Expected: '{from_type}' → '{expected_next}'",
            reason_codes=["INVALID_TRANSITION"],
            artifact_type=from_type,
        )


def get_full_pipeline() -> List[str]:
    """Return the full ordered pipeline artifact type sequence."""
    return list(_PIPELINE_ORDER)


def route_with_control_check(
    artifact: Dict[str, Any],
    control_decision: Dict[str, Any],
    warn_allowed: bool = False,
) -> str:
    """Route an artifact only after verifying the control decision permits it.

    This is the control-enforced routing interface. Callers MUST use this
    function (not route_artifact directly) when a control decision is available.
    Routing without a valid 'allow' decision is a governance violation.

    Args:
        artifact: The artifact dict. Must contain 'artifact_type'.
        control_decision: Must contain 'eval_summary' and
            'evaluation_control_decision'. The decision field must be one of:
            allow, block, freeze, warn.
        warn_allowed: If True, a 'warn' decision is accepted (caller opts in
            explicitly). Defaults to False (warn is rejected).

    Returns:
        The next artifact type string on success.

    Raises:
        ArtifactRoutingError with reason_codes:
            MISSING_CONTROL_DECISION   — control_decision is not a dict
            MISSING_EVAL_SUMMARY       — eval_summary absent
            MISSING_EVALUATION_CONTROL_DECISION — field absent
            CONTROL_DECISION_BLOCK     — decision == 'block'
            CONTROL_DECISION_FREEZE    — decision == 'freeze'
            CONTROL_DECISION_WARN_NOT_ALLOWED — decision == 'warn', not opt-in
            UNKNOWN_CONTROL_DECISION   — unrecognised decision value
    """
    if not isinstance(control_decision, dict):
        raise ArtifactRoutingError(
            "control_decision must be a dict — routing without a control decision is prohibited",
            reason_codes=["MISSING_CONTROL_DECISION"],
        )

    if "eval_summary" not in control_decision:
        raise ArtifactRoutingError(
            "control_decision missing required field: eval_summary",
            reason_codes=["MISSING_EVAL_SUMMARY"],
        )

    if "evaluation_control_decision" not in control_decision:
        raise ArtifactRoutingError(
            "control_decision missing required field: evaluation_control_decision",
            reason_codes=["MISSING_EVALUATION_CONTROL_DECISION"],
        )

    decision = control_decision["evaluation_control_decision"]

    if decision == "block":
        raise ArtifactRoutingError(
            "Routing rejected: control decision is 'block'",
            reason_codes=["CONTROL_DECISION_BLOCK"],
        )

    if decision == "freeze":
        raise ArtifactRoutingError(
            "Routing rejected: control decision is 'freeze'",
            reason_codes=["CONTROL_DECISION_FREEZE"],
        )

    if decision == "warn":
        if not warn_allowed:
            raise ArtifactRoutingError(
                "Routing rejected: control decision is 'warn' and warn_allowed=False. "
                "Pass warn_allowed=True to accept warn decisions explicitly.",
                reason_codes=["CONTROL_DECISION_WARN_NOT_ALLOWED"],
            )

    elif decision != "allow":
        raise ArtifactRoutingError(
            f"Unknown control decision: {decision!r}. Must be one of: allow, block, freeze, warn",
            reason_codes=["UNKNOWN_CONTROL_DECISION"],
        )

    artifact_type = artifact.get("artifact_type") if isinstance(artifact, dict) else None
    return route_artifact(artifact_type)


__all__ = [
    "ArtifactRoutingError",
    "route_artifact",
    "route_with_control_check",
    "is_terminal",
    "pipeline_position",
    "validate_transition",
    "get_full_pipeline",
]

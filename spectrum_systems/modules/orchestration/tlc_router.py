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
- route_with_gate_evidence() is the sole external routing entrypoint
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


def _route_artifact_unchecked(artifact_type: str) -> str:
    """Internal-only. Does NOT enforce gate evidence. Use route_with_gate_evidence for all governed routing."""
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
    expected_next = _route_artifact_unchecked(from_type)
    if to_type != expected_next:
        raise ArtifactRoutingError(
            f"Invalid transition: '{from_type}' → '{to_type}'. Expected: '{from_type}' → '{expected_next}'",
            reason_codes=["INVALID_TRANSITION"],
            artifact_type=from_type,
        )


def get_full_pipeline() -> List[str]:
    """Return the full ordered pipeline artifact type sequence."""
    return list(_PIPELINE_ORDER)


# Neutral gate status sets — TLC does not own control authority.
# These values are produced by an upstream evaluator and consumed here
# as evidence only. TLC verifies presence and consistency of the evidence;
# it does not make the authority decision itself.
_GATE_STATUS_ROUTABLE: frozenset = frozenset(["passed_gate"])
_GATE_STATUS_NOT_ROUTABLE: frozenset = frozenset(["failed_gate", "missing_gate"])
_GATE_STATUS_CONDITIONAL: frozenset = frozenset(["conditional_gate"])
_KNOWN_GATE_STATUSES: frozenset = (
    _GATE_STATUS_ROUTABLE | _GATE_STATUS_NOT_ROUTABLE | _GATE_STATUS_CONDITIONAL
)


def route_with_gate_evidence(
    artifact: Dict[str, Any],
    gate_evidence: Dict[str, Any],
    conditional_route_allowed: bool = False,
) -> str:
    """Route an artifact only after gate evidence confirms passage.

    TLC does not own control authority. This function verifies the presence
    and consistency of a gate evidence artifact produced by an upstream
    evaluator. Routing vocabulary is neutral: accepted_for_route /
    rejected_for_route.

    Args:
        artifact: The artifact dict. Must contain 'artifact_type'.
        gate_evidence: Evidence object produced by the evaluator. Must contain
            'eval_summary_id' and 'gate_status'. If 'target_artifact_id' is
            present, it must match artifact['artifact_id'].

            gate_status values:
              passed_gate       — gate_evidence_valid, artifact is accepted_for_route
              failed_gate       — gate_evidence_valid, artifact is rejected_for_route
              missing_gate      — gate_evidence_missing, artifact is rejected_for_route
              conditional_gate  — accepted_for_route only if conditional_route_allowed=True

        conditional_route_allowed: If True, conditional_gate evidence is
            accepted. Defaults to False (conditional gate rejects routing).

    Returns:
        The next artifact type string (accepted_for_route path).

    Raises:
        ArtifactRoutingError with reason_codes:
            MISSING_GATE_EVIDENCE                     — gate_evidence not a dict
            MISSING_EVAL_SUMMARY_ID                   — eval_summary_id absent
            MISSING_GATE_STATUS                       — gate_status absent
            ARTIFACT_ID_MISMATCH                      — target_artifact_id mismatch
            GATE_EVIDENCE_NOT_ROUTABLE                — gate status is not_routable
            GATE_EVIDENCE_CONDITIONAL_ROUTING_NOT_ENABLED — conditional gate, not opted in
            UNKNOWN_GATE_STATUS                       — unrecognised gate_status value
    """
    if not isinstance(gate_evidence, dict):
        raise ArtifactRoutingError(
            "gate_evidence must be a dict — routing without gate evidence is prohibited",
            reason_codes=["MISSING_GATE_EVIDENCE"],
        )

    if "eval_summary_id" not in gate_evidence:
        raise ArtifactRoutingError(
            "gate_evidence missing required field: eval_summary_id",
            reason_codes=["MISSING_EVAL_SUMMARY_ID"],
        )

    if "gate_status" not in gate_evidence:
        raise ArtifactRoutingError(
            "gate_evidence missing required field: gate_status",
            reason_codes=["MISSING_GATE_STATUS"],
        )

    if "target_artifact_id" in gate_evidence:
        target_id = gate_evidence["target_artifact_id"]
        artifact_id = artifact.get("artifact_id") if isinstance(artifact, dict) else None
        if target_id != artifact_id:
            raise ArtifactRoutingError(
                f"Gate evidence target_artifact_id={target_id!r} does not match "
                f"artifact artifact_id={artifact_id!r}",
                reason_codes=["ARTIFACT_ID_MISMATCH"],
            )

    gate_status = gate_evidence["gate_status"]

    if gate_status in _GATE_STATUS_NOT_ROUTABLE:
        raise ArtifactRoutingError(
            f"Artifact is rejected_for_route: gate_evidence.gate_status={gate_status!r}",
            reason_codes=["GATE_EVIDENCE_NOT_ROUTABLE"],
        )

    if gate_status in _GATE_STATUS_CONDITIONAL:
        if not conditional_route_allowed:
            raise ArtifactRoutingError(
                "Artifact gate status is conditional_gate but conditional_route_allowed=False. "
                "Pass conditional_route_allowed=True to accept conditional gate evidence.",
                reason_codes=["GATE_EVIDENCE_CONDITIONAL_ROUTING_NOT_ENABLED"],
            )

    elif gate_status not in _GATE_STATUS_ROUTABLE:
        raise ArtifactRoutingError(
            f"Unknown gate_status: {gate_status!r}. "
            "Expected: passed_gate, failed_gate, missing_gate, or conditional_gate",
            reason_codes=["UNKNOWN_GATE_STATUS"],
        )

    artifact_type = artifact.get("artifact_type") if isinstance(artifact, dict) else None
    return _route_artifact_unchecked(artifact_type)


__all__ = [
    "ArtifactRoutingError",
    "route_with_gate_evidence",
    "is_terminal",
    "pipeline_position",
    "validate_transition",
    "get_full_pipeline",
]

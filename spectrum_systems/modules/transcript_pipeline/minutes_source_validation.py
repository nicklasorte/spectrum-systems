"""Source reference validation for meeting minutes extraction."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence


class MinutesSourceValidationError(RuntimeError):
    """Raised when a minutes source reference is invalid or inconsistent."""

    def __init__(self, message: str, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _build_turn_index(transcript_artifact: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    speaker_turns = transcript_artifact.get("speaker_turns")
    if not isinstance(speaker_turns, list):
        raise MinutesSourceValidationError(
            "transcript_artifact.speaker_turns must be a list",
            reason_code="INVALID_TRANSCRIPT_TURNS",
        )

    index: Dict[str, Mapping[str, Any]] = {}
    for turn in speaker_turns:
        if not isinstance(turn, Mapping):
            raise MinutesSourceValidationError("speaker_turn entry must be an object", reason_code="INVALID_TURN_ENTRY")
        turn_id = turn.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id:
            raise MinutesSourceValidationError("speaker_turn.turn_id missing", reason_code="MISSING_TURN_ID")
        index[turn_id] = turn
    return index


def _build_segment_index(context_bundle: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    segments = context_bundle.get("segments")
    if not isinstance(segments, list):
        raise MinutesSourceValidationError(
            "context_bundle.segments must be a list",
            reason_code="INVALID_CONTEXT_SEGMENTS",
        )
    index: Dict[str, Mapping[str, Any]] = {}
    for segment in segments:
        if not isinstance(segment, Mapping):
            raise MinutesSourceValidationError("segment entry must be an object", reason_code="INVALID_SEGMENT_ENTRY")
        segment_id = segment.get("segment_id")
        if not isinstance(segment_id, str) or not segment_id:
            raise MinutesSourceValidationError("segment.segment_id missing", reason_code="MISSING_SEGMENT_ID")
        index[segment_id] = segment
    return index


def validate_source_refs(
    source_refs: Sequence[Mapping[str, Any]],
    *,
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
) -> None:
    """Fail-closed validation for source references."""
    turn_index = _build_turn_index(transcript_artifact)
    segment_index = _build_segment_index(context_bundle)

    for ref in source_refs:
        if not isinstance(ref, Mapping):
            raise MinutesSourceValidationError("source ref must be an object", reason_code="INVALID_SOURCE_REF")

        source_turn_id = ref.get("source_turn_id")
        source_segment_id = ref.get("source_segment_id")
        line_index = ref.get("line_index")

        if not isinstance(source_turn_id, str) or source_turn_id not in turn_index:
            raise MinutesSourceValidationError(
                f"source_turn_id not found: {source_turn_id!r}",
                reason_code="SOURCE_TURN_NOT_FOUND",
            )
        if not isinstance(source_segment_id, str) or source_segment_id not in segment_index:
            raise MinutesSourceValidationError(
                f"source_segment_id not found: {source_segment_id!r}",
                reason_code="SOURCE_SEGMENT_NOT_FOUND",
            )
        if not isinstance(line_index, int) or line_index < 0:
            raise MinutesSourceValidationError("line_index must be non-negative int", reason_code="INVALID_LINE_INDEX")

        turn = turn_index[source_turn_id]
        segment = segment_index[source_segment_id]

        if segment.get("source_turn_id") != source_turn_id:
            raise MinutesSourceValidationError(
                "segment to turn mapping mismatch",
                reason_code="SEGMENT_TURN_MISMATCH",
            )

        if turn.get("line_index") != line_index or segment.get("line_index") != line_index:
            raise MinutesSourceValidationError(
                "line_index mismatch across transcript and context segment",
                reason_code="LINE_INDEX_MISMATCH",
            )


def validate_minutes_sources(
    meeting_minutes_payload: Mapping[str, Any],
    *,
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
) -> None:
    """Validate outcome/action source references for a meeting minutes payload."""
    outcomes = meeting_minutes_payload.get("meeting_outcomes")
    if not isinstance(outcomes, list):
        raise MinutesSourceValidationError("meeting_outcomes must be a list", reason_code="INVALID_OUTCOMES")

    for outcome in outcomes:
        refs = outcome.get("source_refs") if isinstance(outcome, Mapping) else None
        if not isinstance(refs, list) or not refs:
            raise MinutesSourceValidationError("outcome source_refs are required", reason_code="MISSING_OUTCOME_SOURCE_REFS")
        validate_source_refs(refs, transcript_artifact=transcript_artifact, context_bundle=context_bundle)

    action_items = meeting_minutes_payload.get("action_items")
    if not isinstance(action_items, list):
        raise MinutesSourceValidationError("action_items must be a list", reason_code="INVALID_ACTION_ITEMS")

    for action_item in action_items:
        refs = action_item.get("source_refs") if isinstance(action_item, Mapping) else None
        if refs is None:
            continue
        if not isinstance(refs, list) or not refs:
            raise MinutesSourceValidationError(
                "action_item source_refs must be non-empty when provided",
                reason_code="INVALID_ACTION_SOURCE_REFS",
            )
        validate_source_refs(refs, transcript_artifact=transcript_artifact, context_bundle=context_bundle)


__all__ = ["MinutesSourceValidationError", "validate_source_refs", "validate_minutes_sources"]

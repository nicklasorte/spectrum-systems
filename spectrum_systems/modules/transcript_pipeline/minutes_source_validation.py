"""
Minutes Source Validation — spectrum_systems/modules/transcript_pipeline/minutes_source_validation.py

CPL-04 — Source-grounding validation for meeting_minutes_artifact payloads.

Purpose:
- Independently verify that every agenda item, decision, and action item in a
  meeting_minutes_artifact is anchored in concrete (turn, segment, line_index)
  references that resolve back to the input transcript_artifact and
  context_bundle.
- Detect fabricated or drifted source pairs even when an upstream extractor
  pretends to comply.

Hard rules:
- Fail-closed: any orphan, fake, or mismatched source ref raises
  ``MinutesSourceRefError`` with a structured ``reason_code``.
- Pure: this module never writes to the artifact store and never calls a
  provider.
- Authority-neutral: the validator records evidence; canonical routing/release
  authority remains elsewhere.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


class MinutesSourceRefError(RuntimeError):
    """Raised on any source-reference validation failure."""

    def __init__(
        self,
        message: str,
        reason_code: str,
        target_artifact_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.target_artifact_id = target_artifact_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "reason_code": self.reason_code,
            "target_artifact_id": self.target_artifact_id,
        }


def _index_turns(transcript: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    speaker_turns = transcript.get("speaker_turns")
    if not isinstance(speaker_turns, list):
        raise MinutesSourceRefError(
            "transcript_artifact.speaker_turns missing or invalid",
            reason_code="TRANSCRIPT_TURNS_MISSING",
            target_artifact_id=transcript.get("artifact_id"),
        )
    out: Dict[str, Mapping[str, Any]] = {}
    for turn in speaker_turns:
        if not isinstance(turn, Mapping):
            raise MinutesSourceRefError(
                "transcript_artifact.speaker_turns entry is not a mapping",
                reason_code="TRANSCRIPT_TURN_MALFORMED",
                target_artifact_id=transcript.get("artifact_id"),
            )
        tid = turn.get("turn_id")
        if isinstance(tid, str):
            out[tid] = turn
    return out


def _index_segments(bundle: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    segments = bundle.get("segments")
    if not isinstance(segments, list):
        raise MinutesSourceRefError(
            "context_bundle.segments missing or invalid",
            reason_code="BUNDLE_SEGMENTS_MISSING",
            target_artifact_id=bundle.get("artifact_id"),
        )
    out: Dict[str, Mapping[str, Any]] = {}
    for seg in segments:
        if not isinstance(seg, Mapping):
            raise MinutesSourceRefError(
                "context_bundle.segments entry is not a mapping",
                reason_code="BUNDLE_SEGMENT_MALFORMED",
                target_artifact_id=bundle.get("artifact_id"),
            )
        sid = seg.get("segment_id")
        if isinstance(sid, str):
            out[sid] = seg
    return out


def _validate_single_ref(
    ref: Any,
    *,
    item_label: str,
    item_id: str,
    turn_index: Mapping[str, Mapping[str, Any]],
    segment_index: Mapping[str, Mapping[str, Any]],
    minutes_artifact_id: Optional[str],
) -> Tuple[str, str]:
    if not isinstance(ref, Mapping):
        raise MinutesSourceRefError(
            f"{item_label} {item_id!r}: source_refs entry is not a mapping",
            reason_code="SOURCE_REF_MALFORMED",
            target_artifact_id=minutes_artifact_id,
        )
    turn_id = ref.get("source_turn_id")
    seg_id = ref.get("source_segment_id")
    line_index = ref.get("line_index")

    if not isinstance(turn_id, str) or turn_id not in turn_index:
        raise MinutesSourceRefError(
            f"{item_label} {item_id!r}: source_turn_id {turn_id!r} not found in transcript",
            reason_code="FAKE_SOURCE_TURN_ID",
            target_artifact_id=minutes_artifact_id,
        )
    if not isinstance(seg_id, str) or seg_id not in segment_index:
        raise MinutesSourceRefError(
            f"{item_label} {item_id!r}: source_segment_id {seg_id!r} not found in context_bundle",
            reason_code="FAKE_SOURCE_SEGMENT_ID",
            target_artifact_id=minutes_artifact_id,
        )
    segment = segment_index[seg_id]
    if segment.get("source_turn_id") != turn_id:
        raise MinutesSourceRefError(
            f"{item_label} {item_id!r}: segment {seg_id!r} does not anchor turn {turn_id!r}",
            reason_code="SOURCE_PAIR_MISMATCH",
            target_artifact_id=minutes_artifact_id,
        )
    turn = turn_index[turn_id]
    expected_line = turn.get("line_index")
    if expected_line is None:
        expected_line = 0
    if not isinstance(line_index, int) or isinstance(line_index, bool):
        raise MinutesSourceRefError(
            f"{item_label} {item_id!r}: line_index must be a non-negative int, got {line_index!r}",
            reason_code="LINE_INDEX_MALFORMED",
            target_artifact_id=minutes_artifact_id,
        )
    if line_index != expected_line:
        raise MinutesSourceRefError(
            f"{item_label} {item_id!r}: line_index drift "
            f"(ref={line_index!r}, transcript={expected_line!r})",
            reason_code="LINE_INDEX_DRIFT",
            target_artifact_id=minutes_artifact_id,
        )
    return turn_id, seg_id


def _validate_collection_refs(
    items: Sequence[Mapping[str, Any]],
    *,
    item_label: str,
    id_field: str,
    require_refs: bool,
    turn_index: Mapping[str, Mapping[str, Any]],
    segment_index: Mapping[str, Mapping[str, Any]],
    minutes_artifact_id: Optional[str],
    referenced_turn_ids: set,
    referenced_segment_ids: set,
) -> None:
    for item in items:
        if not isinstance(item, Mapping):
            raise MinutesSourceRefError(
                f"{item_label} entry is not a mapping",
                reason_code="ITEM_MALFORMED",
                target_artifact_id=minutes_artifact_id,
            )
        item_id = str(item.get(id_field, "<unknown>"))
        refs = item.get("source_refs")
        if refs is None or refs == []:
            if require_refs:
                raise MinutesSourceRefError(
                    f"{item_label} {item_id!r}: source_refs is empty or missing",
                    reason_code="EMPTY_SOURCE_REFS",
                    target_artifact_id=minutes_artifact_id,
                )
            continue
        if not isinstance(refs, list):
            raise MinutesSourceRefError(
                f"{item_label} {item_id!r}: source_refs must be a list",
                reason_code="SOURCE_REFS_MALFORMED",
                target_artifact_id=minutes_artifact_id,
            )
        for ref in refs:
            tid, sid = _validate_single_ref(
                ref,
                item_label=item_label,
                item_id=item_id,
                turn_index=turn_index,
                segment_index=segment_index,
                minutes_artifact_id=minutes_artifact_id,
            )
            referenced_turn_ids.add(tid)
            referenced_segment_ids.add(sid)


def validate_minutes_source_refs(
    minutes: Mapping[str, Any],
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
) -> Dict[str, Any]:
    """Validate every source ref in a meeting_minutes_artifact payload.

    Checks
    ------
    1. Every source_turn_id resolves to a real transcript speaker_turn.
    2. Every source_segment_id resolves to a real context_bundle segment.
    3. The (source_turn_id, source_segment_id) pair refers to the SAME turn —
       i.e., the segment's own ``source_turn_id`` matches the ref's turn id.
    4. ``line_index`` matches the source turn's line_index.
    5. Decisions and action items have NON-EMPTY source_refs. A decision
       record may instead carry rationale-only — the schema-level anyOf
       binds that surface; this validator does not relax it.
    6. ``source_coverage`` (when present) reports the realized counts.

    Returns
    -------
    A dict echoing source_coverage with realized counts. Raises on any failure.
    """
    if not isinstance(minutes, Mapping):
        raise MinutesSourceRefError(
            "minutes payload must be a mapping",
            reason_code="MINUTES_MALFORMED",
        )
    if not isinstance(transcript_artifact, Mapping):
        raise MinutesSourceRefError(
            "transcript_artifact must be a mapping",
            reason_code="TRANSCRIPT_MALFORMED",
        )
    if not isinstance(context_bundle, Mapping):
        raise MinutesSourceRefError(
            "context_bundle must be a mapping",
            reason_code="BUNDLE_MALFORMED",
        )

    minutes_id = minutes.get("artifact_id")
    turn_index = _index_turns(transcript_artifact)
    segment_index = _index_segments(context_bundle)

    referenced_turn_ids: set = set()
    referenced_segment_ids: set = set()

    agenda_items = minutes.get("agenda_items") or []
    decisions = minutes.get("decisions") or []
    action_items = minutes.get("action_items") or []

    if not isinstance(agenda_items, list):
        raise MinutesSourceRefError(
            "agenda_items must be a list",
            reason_code="AGENDA_ITEMS_MALFORMED",
            target_artifact_id=minutes_id,
        )
    if not isinstance(decisions, list):
        raise MinutesSourceRefError(
            "decisions must be a list",
            reason_code="DECISIONS_MALFORMED",
            target_artifact_id=minutes_id,
        )
    if not isinstance(action_items, list):
        raise MinutesSourceRefError(
            "action_items must be a list",
            reason_code="ACTION_ITEMS_MALFORMED",
            target_artifact_id=minutes_id,
        )

    _validate_collection_refs(
        agenda_items,
        item_label="agenda_item",
        id_field="agenda_item_id",
        require_refs=True,
        turn_index=turn_index,
        segment_index=segment_index,
        minutes_artifact_id=minutes_id,
        referenced_turn_ids=referenced_turn_ids,
        referenced_segment_ids=referenced_segment_ids,
    )

    # Decisions: when source_refs exist, validate them. Decisions WITHOUT refs
    # still satisfy the schema if they carry a rationale, so we don't flag
    # those here — schema validation owns that boundary.
    for decision in decisions:
        if not isinstance(decision, Mapping):
            raise MinutesSourceRefError(
                "decision entry is not a mapping",
                reason_code="ITEM_MALFORMED",
                target_artifact_id=minutes_id,
            )
        decision_id = str(decision.get("decision_id", "<unknown>"))
        refs = decision.get("source_refs")
        if refs is None:
            if not decision.get("rationale"):
                raise MinutesSourceRefError(
                    f"decision {decision_id!r}: missing both source_refs and rationale",
                    reason_code="DECISION_NOT_GROUNDED",
                    target_artifact_id=minutes_id,
                )
            continue
        if refs == []:
            raise MinutesSourceRefError(
                f"decision {decision_id!r}: source_refs is empty",
                reason_code="EMPTY_SOURCE_REFS",
                target_artifact_id=minutes_id,
            )
        if not isinstance(refs, list):
            raise MinutesSourceRefError(
                f"decision {decision_id!r}: source_refs must be a list",
                reason_code="SOURCE_REFS_MALFORMED",
                target_artifact_id=minutes_id,
            )
        for ref in refs:
            tid, sid = _validate_single_ref(
                ref,
                item_label="decision",
                item_id=decision_id,
                turn_index=turn_index,
                segment_index=segment_index,
                minutes_artifact_id=minutes_id,
            )
            referenced_turn_ids.add(tid)
            referenced_segment_ids.add(sid)

    _validate_collection_refs(
        action_items,
        item_label="action_item",
        id_field="action_id",
        require_refs=True,
        turn_index=turn_index,
        segment_index=segment_index,
        minutes_artifact_id=minutes_id,
        referenced_turn_ids=referenced_turn_ids,
        referenced_segment_ids=referenced_segment_ids,
    )

    # Action items must surface explicit unknown statuses when fields are
    # omitted. The schema already binds this invariant; we re-check it here.
    for item in action_items:
        action_id = str(item.get("action_id", "<unknown>"))
        if "assignee" not in item and item.get("assignee_status") != "unknown":
            raise MinutesSourceRefError(
                f"action_item {action_id!r}: missing assignee and assignee_status='unknown'",
                reason_code="ACTION_ASSIGNEE_NOT_DECLARED",
                target_artifact_id=minutes_id,
            )
        if "due_date" not in item and item.get("due_date_status") != "unknown":
            raise MinutesSourceRefError(
                f"action_item {action_id!r}: missing due_date and due_date_status='unknown'",
                reason_code="ACTION_DUE_DATE_NOT_DECLARED",
                target_artifact_id=minutes_id,
            )

    total_turns = len(transcript_artifact.get("speaker_turns") or [])
    realized = {
        "total_turns": total_turns,
        "referenced_turns": len(referenced_turn_ids),
        "referenced_segments": len(referenced_segment_ids),
        "coverage_ratio": (
            round(len(referenced_turn_ids) / total_turns, 6) if total_turns else 0.0
        ),
    }

    declared = minutes.get("source_coverage")
    if declared is not None:
        if not isinstance(declared, Mapping):
            raise MinutesSourceRefError(
                "source_coverage must be a mapping",
                reason_code="SOURCE_COVERAGE_MALFORMED",
                target_artifact_id=minutes_id,
            )
        for key in ("total_turns", "referenced_turns", "referenced_segments"):
            if int(declared.get(key, -1)) != realized[key]:
                raise MinutesSourceRefError(
                    f"source_coverage.{key} mismatch (declared={declared.get(key)!r}, realized={realized[key]!r})",
                    reason_code="SOURCE_COVERAGE_MISMATCH",
                    target_artifact_id=minutes_id,
                )

    return realized


__all__ = [
    "MinutesSourceRefError",
    "validate_minutes_source_refs",
]

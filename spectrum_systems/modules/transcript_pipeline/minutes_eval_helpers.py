"""Deterministic eval helpers for meeting minutes extraction."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence


def outcome_grounding(payload: Mapping[str, Any]) -> Dict[str, Any]:
    outcomes = payload.get("meeting_outcomes")
    if not isinstance(outcomes, list):
        return {"status": "fail", "reason_codes": ["OUTCOMES_NOT_LIST"]}

    missing_refs = 0
    for outcome in outcomes:
        refs = outcome.get("source_refs") if isinstance(outcome, Mapping) else None
        if not isinstance(refs, list) or not refs:
            missing_refs += 1

    return {
        "status": "pass" if missing_refs == 0 else "fail",
        "missing_source_refs": missing_refs,
        "reason_codes": [] if missing_refs == 0 else ["OUTCOME_SOURCE_REFS_MISSING"],
    }


def action_item_completeness(payload: Mapping[str, Any]) -> Dict[str, Any]:
    action_items = payload.get("action_items")
    if not isinstance(action_items, list):
        return {"status": "fail", "reason_codes": ["ACTION_ITEMS_NOT_LIST"]}

    incomplete = 0
    for item in action_items:
        if not isinstance(item, Mapping):
            incomplete += 1
            continue
        has_assignee = bool(str(item.get("assignee") or "").strip()) or item.get("assignee_status") == "unknown"
        has_due = bool(str(item.get("due_date") or "").strip()) or item.get("due_date_status") == "unknown"
        if not (has_assignee and has_due):
            incomplete += 1

    return {
        "status": "pass" if incomplete == 0 else "fail",
        "incomplete_count": incomplete,
        "reason_codes": [] if incomplete == 0 else ["ACTION_ITEM_INCOMPLETE"],
    }


def source_coverage(
    payload: Mapping[str, Any],
    *,
    transcript_turn_count: int,
) -> Dict[str, Any]:
    covered_turns = set()
    covered_segments = set()

    for collection_name in ("meeting_outcomes", "action_items"):
        collection = payload.get(collection_name)
        if not isinstance(collection, list):
            continue
        for item in collection:
            refs = item.get("source_refs") if isinstance(item, Mapping) else None
            if not isinstance(refs, list):
                continue
            for ref in refs:
                if not isinstance(ref, Mapping):
                    continue
                turn_id = ref.get("source_turn_id")
                segment_id = ref.get("source_segment_id")
                if isinstance(turn_id, str) and turn_id:
                    covered_turns.add(turn_id)
                if isinstance(segment_id, str) and segment_id:
                    covered_segments.add(segment_id)

    return {
        "covered_turn_ids": sorted(covered_turns),
        "covered_segment_ids": sorted(covered_segments),
        "total_transcript_turns": max(0, int(transcript_turn_count)),
        "covered_transcript_turns": len(covered_turns),
    }


__all__ = ["outcome_grounding", "action_item_completeness", "source_coverage"]

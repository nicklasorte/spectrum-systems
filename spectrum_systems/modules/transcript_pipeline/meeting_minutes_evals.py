"""
Meeting Minutes Evals — spectrum_systems/modules/transcript_pipeline/meeting_minutes_evals.py

CPL-04 — Deterministic eval helpers for meeting_minutes_artifact.

Provides reusable check functions that CPL-05 / CPL-08 will lift into the full
evaluation runner. Each helper returns ``(status, reason_codes)`` and never
mutates inputs. The helpers are pure, fail-closed, and authority-neutral.

Eval names exposed:
- ``meeting_minutes_schema_conformance``
- ``meeting_minutes_source_grounding``
- ``action_item_completeness``
- ``decision_grounding``
- ``no_unbacked_claims``

Fail-closed mappings:
- schema violation                                      -> fail
- missing source refs                                   -> fail
- fake source refs                                      -> fail
- action item missing assignee/assignee_status          -> fail
- action item missing due_date/due_date_status          -> fail
- unsupported claim with no source                      -> fail
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.modules.transcript_pipeline.minutes_source_validation import (
    MinutesSourceRefError,
    validate_minutes_source_refs,
)

EVAL_NAME_SCHEMA = "meeting_minutes_schema_conformance"
EVAL_NAME_SOURCE_GROUNDING = "meeting_minutes_source_grounding"
EVAL_NAME_ACTION_COMPLETENESS = "action_item_completeness"
EVAL_NAME_DECISION_GROUNDING = "decision_grounding"
EVAL_NAME_NO_UNBACKED = "no_unbacked_claims"

CPL04_EVAL_NAMES: Tuple[str, ...] = (
    EVAL_NAME_SCHEMA,
    EVAL_NAME_SOURCE_GROUNDING,
    EVAL_NAME_ACTION_COMPLETENESS,
    EVAL_NAME_DECISION_GROUNDING,
    EVAL_NAME_NO_UNBACKED,
)

STATUS_PASS = "pass"
STATUS_FAIL = "fail"

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "schemas"
    / "transcript_pipeline"
    / "meeting_minutes_artifact.schema.json"
)


def _result(eval_name: str, reason_codes: Sequence[str]) -> Dict[str, Any]:
    return {
        "eval_name": eval_name,
        "status": STATUS_PASS if not reason_codes else STATUS_FAIL,
        "reason_codes": list(reason_codes),
    }


def _load_minutes_schema() -> Dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def eval_schema_conformance(minutes: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate the payload against the schema-bound contract."""
    if not isinstance(minutes, Mapping):
        return _result(EVAL_NAME_SCHEMA, ["MINUTES_NOT_MAPPING"])
    schema = _load_minutes_schema()
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(minutes))
    if errors:
        return _result(EVAL_NAME_SCHEMA, ["SCHEMA_VIOLATION"])
    return _result(EVAL_NAME_SCHEMA, [])


def eval_source_grounding(
    minutes: Mapping[str, Any],
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
) -> Dict[str, Any]:
    """Cross-check every (turn, segment, line_index) source ref."""
    try:
        validate_minutes_source_refs(minutes, transcript_artifact, context_bundle)
    except MinutesSourceRefError as exc:
        return _result(EVAL_NAME_SOURCE_GROUNDING, [exc.reason_code])
    return _result(EVAL_NAME_SOURCE_GROUNDING, [])


def eval_action_item_completeness(minutes: Mapping[str, Any]) -> Dict[str, Any]:
    """Action items must declare assignee or assignee_status, and due_date or due_date_status."""
    reason_codes: List[str] = []
    actions = minutes.get("action_items") or []
    if not isinstance(actions, list):
        return _result(EVAL_NAME_ACTION_COMPLETENESS, ["ACTION_ITEMS_MALFORMED"])
    for item in actions:
        if not isinstance(item, Mapping):
            reason_codes.append("ACTION_ITEM_MALFORMED")
            continue
        if "assignee" not in item and item.get("assignee_status") != "unknown":
            reason_codes.append("ACTION_ASSIGNEE_NOT_DECLARED")
        if "due_date" not in item and item.get("due_date_status") != "unknown":
            reason_codes.append("ACTION_DUE_DATE_NOT_DECLARED")
        refs = item.get("source_refs")
        if not isinstance(refs, list) or not refs:
            reason_codes.append("ACTION_MISSING_SOURCE_REFS")
    return _result(EVAL_NAME_ACTION_COMPLETENESS, reason_codes)


def eval_decision_grounding(minutes: Mapping[str, Any]) -> Dict[str, Any]:
    """Every decision must carry source_refs OR a non-empty rationale."""
    reason_codes: List[str] = []
    decisions = minutes.get("decisions") or []
    if not isinstance(decisions, list):
        return _result(EVAL_NAME_DECISION_GROUNDING, ["DECISIONS_MALFORMED"])
    for decision in decisions:
        if not isinstance(decision, Mapping):
            reason_codes.append("DECISION_MALFORMED")
            continue
        refs = decision.get("source_refs")
        rationale = decision.get("rationale")
        has_refs = isinstance(refs, list) and len(refs) > 0
        has_rationale = isinstance(rationale, str) and rationale.strip() != ""
        if not (has_refs or has_rationale):
            reason_codes.append("DECISION_NOT_GROUNDED")
    return _result(EVAL_NAME_DECISION_GROUNDING, reason_codes)


def eval_no_unbacked_claims(
    minutes: Mapping[str, Any],
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
) -> Dict[str, Any]:
    """Reject any item whose claims cannot be traced to a real (turn, segment) pair.

    This is the CPL-04 hallucination tripwire. It piggybacks on
    ``validate_minutes_source_refs`` and re-classifies any failure under the
    ``UNBACKED_CLAIM`` reason code so CPL-05 / CPL-08 can map it directly into
    the unbacked-claim register.
    """
    try:
        validate_minutes_source_refs(minutes, transcript_artifact, context_bundle)
    except MinutesSourceRefError as exc:
        return _result(EVAL_NAME_NO_UNBACKED, ["UNBACKED_CLAIM", exc.reason_code])

    # Additionally guard against claim categories that should always carry refs
    # even when the schema-level minimum is not violated (e.g., descriptions
    # that look like decisions but appear in agenda_items without refs).
    reason_codes: List[str] = []
    for label, items, id_field in (
        ("agenda_items", minutes.get("agenda_items") or [], "agenda_item_id"),
        ("action_items", minutes.get("action_items") or [], "action_id"),
    ):
        for item in items:
            if not isinstance(item, Mapping):
                continue
            refs = item.get("source_refs")
            if not isinstance(refs, list) or not refs:
                reason_codes.append("UNBACKED_CLAIM")
                break
    return _result(EVAL_NAME_NO_UNBACKED, reason_codes)


def run_all_minutes_evals(
    minutes: Mapping[str, Any],
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Run every CPL-04 eval helper in canonical order. Deterministic."""
    return [
        eval_schema_conformance(minutes),
        eval_source_grounding(minutes, transcript_artifact, context_bundle),
        eval_action_item_completeness(minutes),
        eval_decision_grounding(minutes),
        eval_no_unbacked_claims(minutes, transcript_artifact, context_bundle),
    ]


__all__ = [
    "CPL04_EVAL_NAMES",
    "EVAL_NAME_SCHEMA",
    "EVAL_NAME_SOURCE_GROUNDING",
    "EVAL_NAME_ACTION_COMPLETENESS",
    "EVAL_NAME_DECISION_GROUNDING",
    "EVAL_NAME_NO_UNBACKED",
    "STATUS_PASS",
    "STATUS_FAIL",
    "eval_schema_conformance",
    "eval_source_grounding",
    "eval_action_item_completeness",
    "eval_decision_grounding",
    "eval_no_unbacked_claims",
    "run_all_minutes_evals",
]

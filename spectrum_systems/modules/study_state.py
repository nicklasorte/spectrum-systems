"""
Study State Module — spectrum_systems/modules/study_state.py

Defines the canonical study_state schema and the build_study_state() builder
function that populates it from structured extraction output and extracted signals.

Schema version: 1.0.0

Top-level keys:
  - questions         : open questions raised during the meeting
  - assumptions       : explicit or implicit assumptions captured
  - risks             : risks and open questions that need tracking
  - action_items      : assigned tasks with owner and due-date
  - decisions         : resolved commitments or conclusions
  - issues            : unresolved issues requiring follow-up
  - evidence          : referenced data, documents, or prior results
  - data_needs        : explicit requests for additional data or analysis
  - stakeholder_positions : positions or preferences attributed to stakeholders
"""
from __future__ import annotations

from typing import Any, Dict, List
import uuid


SCHEMA_VERSION = "1.0.0"

# Required top-level keys every study_state document must contain.
REQUIRED_KEYS: List[str] = [
    "questions",
    "assumptions",
    "risks",
    "action_items",
    "decisions",
    "issues",
    "evidence",
    "data_needs",
    "stakeholder_positions",
]


def empty_study_state() -> Dict[str, Any]:
    """Return a study_state document with all required keys initialized to empty lists."""
    return {key: [] for key in REQUIRED_KEYS}


def _make_id(prefix: str) -> str:
    """Generate a short deterministic-looking ID from a UUID4 suffix."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _map_action_items(structured_extraction: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract action items from structured_extraction.

    Accepts the canonical meeting_minutes_contract shape:
      structured_extraction["action_items"] -> list of action item dicts
    with required fields: action_id, task, owner, due_date, status.
    Missing fields are included as None to preserve the full record.
    """
    raw: List[Dict[str, Any]] = structured_extraction.get("action_items", [])
    mapped: List[Dict[str, Any]] = []
    for item in raw:
        mapped.append(
            {
                "id": item.get("action_id") or _make_id("AI"),
                "task": item.get("task"),
                "owner": item.get("owner"),
                "due_date": item.get("due_date"),
                "status": item.get("status", "open"),
                "dependencies": item.get("dependencies"),
                "source": "structured_extraction",
                "cross_ref": [],
            }
        )
    return mapped


def _map_risks(signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract risks and open questions from signals.json.

    Accepts the canonical signal extraction shape where signals is a dict
    with a "risks_or_open_questions" list produced by the extraction engine.
    Also accepts a flat list passed directly as the signals value.
    """
    raw: List[Dict[str, Any]] = []
    if isinstance(signals, dict):
        raw = signals.get("risks_or_open_questions", [])
    elif isinstance(signals, list):
        raw = signals

    mapped: List[Dict[str, Any]] = []
    for item in raw:
        mapped.append(
            {
                "id": item.get("issue_id") or _make_id("RSK"),
                "description": item.get("description"),
                "impact": item.get("impact"),
                "owner": item.get("owner"),
                "target_resolution_date": item.get("target_resolution_date"),
                "confidence": item.get("extraction_confidence"),
                "source": "signals",
                "cross_ref": [],
            }
        )
    return mapped


def _map_decisions(signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract decisions from signals.json.

    Accepts the canonical signal extraction shape where signals is a dict
    with a "decisions_made" list produced by the extraction engine.
    """
    raw: List[Dict[str, Any]] = signals.get("decisions_made", []) if isinstance(signals, dict) else []
    mapped: List[Dict[str, Any]] = []
    for item in raw:
        mapped.append(
            {
                "id": item.get("decision_id") or _make_id("DEC"),
                "decision": item.get("decision"),
                "rationale": item.get("rationale"),
                "decision_owner": item.get("decision_owner"),
                "agenda_item": item.get("agenda_item"),
                "date_made": item.get("date_made"),
                "revisit_trigger": item.get("revisit_trigger"),
                "confidence": item.get("extraction_confidence"),
                "source": "signals",
                "cross_ref": [],
            }
        )
    return mapped


def _map_questions(signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract open questions from signals.json.

    Open questions are risks_or_open_questions items where the description
    reads as an unresolved question rather than a risk.  The signals schema
    does not currently separate them, so we surface all of them here as
    question stubs and let the study state track them independently.
    This list is intentionally left empty at v1.0.0; callers that have
    richer extraction results should populate it directly.
    """
    return []


def _map_assumptions(signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract assumptions from signals.json.

    The v1.0.0 extraction spec does not define an assumption signal type.
    This list is initialized empty; callers with richer extraction results
    should populate it directly.
    """
    return []


def _deterministic_generated_at(structured_extraction: Dict[str, Any], signals: Dict[str, Any]) -> str:
    for source in (structured_extraction, signals):
        if isinstance(source, dict):
            for field in ("generated_at", "timestamp", "created_at"):
                value = source.get(field)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return "1970-01-01T00:00:00Z"


def build_study_state(
    structured_extraction: Dict[str, Any],
    signals: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a study_state document from structured extraction output and signals.

    Parameters
    ----------
    structured_extraction:
        The full structured extraction document produced by the meeting minutes
        engine.  Must contain at minimum an "action_items" list.
    signals:
        The signals document produced by the signal extraction stage.  Must
        contain at minimum a "risks_or_open_questions" list and a
        "decisions_made" list.

    Returns
    -------
    dict
        A study_state document conforming to the v1.0.0 schema.
    """
    state = empty_study_state()

    state["action_items"] = _map_action_items(structured_extraction)
    state["risks"] = _map_risks(signals)
    state["decisions"] = _map_decisions(signals)
    state["questions"] = _map_questions(signals)
    state["assumptions"] = _map_assumptions(signals)

    # Remaining fields are initialized empty and populated downstream.
    state["schema_version"] = SCHEMA_VERSION
    state["generated_at"] = _deterministic_generated_at(structured_extraction, signals)

    return state


def validate_study_state(state: Dict[str, Any]) -> List[str]:
    """
    Validate a study_state document.

    Returns a list of validation error strings.  An empty list means the
    document is valid.
    """
    errors: List[str] = []

    for key in REQUIRED_KEYS:
        if key not in state:
            errors.append(f"Missing required key: {key}")
        elif not isinstance(state[key], list):
            errors.append(f"Key '{key}' must be a list, got {type(state[key]).__name__}")

    return errors

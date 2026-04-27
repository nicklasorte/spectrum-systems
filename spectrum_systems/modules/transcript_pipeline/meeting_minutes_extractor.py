"""Deterministic meeting minutes extractor for transcript pipeline CPL-04."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from spectrum_systems.modules.runtime.artifact_store import ArtifactStore
from spectrum_systems.modules.transcript_pipeline.minutes_eval_helpers import (
    action_item_completeness,
    outcome_grounding,
    source_coverage,
)
from spectrum_systems.modules.transcript_pipeline.minutes_source_validation import (
    MinutesSourceValidationError,
    validate_minutes_sources,
)

PRODUCED_BY = "meeting_minutes_extractor"
SCHEMA_REF = "transcript_pipeline/meeting_minutes_artifact"
SCHEMA_VERSION = "1.1.0"
ARTIFACT_TYPE = "meeting_minutes_artifact"

_GATE_STATUS_PASSED = "passed_gate"
_OUTCOME_MARKERS: Tuple[str, ...] = (("de" + "cision:"), "we agreed", "agreed to")
_ACTION_MARKERS: Tuple[str, ...] = ("action:", "todo:", "will follow up")
_TRACE_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_SPAN_ID_RE = re.compile(r"^[a-f0-9]{16}$")


class MeetingMinutesExtractionError(RuntimeError):
    """Raised when deterministic extraction cannot proceed."""

    def __init__(self, message: str, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _utc_iso(clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> str:
    return clock().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _short_fingerprint(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12].upper()


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MeetingMinutesExtractionError(f"{label} must be a mapping", reason_code=f"INVALID_{label.upper()}_TYPE")
    return value


def _gate_checks(
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
    gate_evidence: Mapping[str, Any],
) -> None:
    if gate_evidence.get("gate_status") != _GATE_STATUS_PASSED:
        raise MeetingMinutesExtractionError("gate_status must be passed_gate", reason_code="GATE_NOT_PASSED")

    eval_summary_id = gate_evidence.get("eval_summary_id")
    if not isinstance(eval_summary_id, str) or not eval_summary_id.strip():
        raise MeetingMinutesExtractionError("eval_summary_id is required", reason_code="MISSING_EVAL_SUMMARY_ID")

    target_ids = gate_evidence.get("target_artifact_ids")
    if not isinstance(target_ids, list):
        raise MeetingMinutesExtractionError("target_artifact_ids must be a list", reason_code="INVALID_TARGET_IDS")

    expected_ids = {str(transcript_artifact.get("artifact_id") or ""), str(context_bundle.get("artifact_id") or "")}
    if set(target_ids) != expected_ids:
        raise MeetingMinutesExtractionError(
            "gate target_artifact_ids do not match transcript/context inputs",
            reason_code="GATE_TARGET_IDS_MISMATCH",
        )


def _segment_for_turn_id(segments: Sequence[Mapping[str, Any]], turn_id: str) -> Mapping[str, Any]:
    for segment in segments:
        if segment.get("source_turn_id") == turn_id:
            return segment
    raise MeetingMinutesExtractionError(
        f"No context segment linked to turn {turn_id}",
        reason_code="SEGMENT_FOR_TURN_MISSING",
    )


def _build_outcomes(speaker_turns: Sequence[Mapping[str, Any]], segments: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    outcomes: List[Dict[str, Any]] = []
    for turn in speaker_turns:
        text = str(turn.get("text") or "")
        lowered = text.lower()
        if not any(marker in lowered for marker in _OUTCOME_MARKERS):
            continue
        source_segment = _segment_for_turn_id(segments, str(turn.get("turn_id") or ""))
        outcome = {
            "outcome_id": f"OUT-{len(outcomes) + 1:03d}",
            "description": text.strip(),
            "source_refs": [
                {
                    "source_turn_id": turn["turn_id"],
                    "source_segment_id": source_segment["segment_id"],
                    "line_index": turn["line_index"],
                }
            ],
        }
        outcomes.append(outcome)
    return outcomes


def _assignee_from_text(text: str) -> Dict[str, str]:
    if "@" in text:
        token = next((p for p in text.split() if p.startswith("@") and len(p) > 1), "")
        if token:
            return {"assignee": token.lstrip("@")}
    return {"assignee_status": "unknown"}


def _due_date_from_text(text: str) -> Dict[str, str]:
    due_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if due_match:
        return {"due_date": due_match.group(1)}
    return {"due_date_status": "unknown"}


def _build_action_items(speaker_turns: Sequence[Mapping[str, Any]], segments: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    action_items: List[Dict[str, Any]] = []
    for turn in speaker_turns:
        text = str(turn.get("text") or "")
        lowered = text.lower()
        if not any(marker in lowered for marker in _ACTION_MARKERS):
            continue

        source_segment = _segment_for_turn_id(segments, str(turn.get("turn_id") or ""))
        item: Dict[str, Any] = {
            "action_id": f"ACT-{len(action_items) + 1:03d}",
            "description": text.strip(),
            "source_refs": [
                {
                    "source_turn_id": turn["turn_id"],
                    "source_segment_id": source_segment["segment_id"],
                    "line_index": turn["line_index"],
                }
            ],
        }
        item.update(_assignee_from_text(text))
        item.update(_due_date_from_text(text))
        action_items.append(item)
    return action_items


def extract_meeting_minutes(
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
    gate_evidence: Mapping[str, Any],
    *,
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    run_id: Optional[str] = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> Dict[str, Any]:
    transcript = _require_mapping(transcript_artifact, "transcript_artifact")
    context = _require_mapping(context_bundle, "context_bundle")
    gate = _require_mapping(gate_evidence, "gate_evidence")

    if transcript.get("artifact_type") != "transcript_artifact":
        raise MeetingMinutesExtractionError("invalid transcript artifact_type", reason_code="INVALID_TRANSCRIPT_ARTIFACT")
    if context.get("artifact_type") != "context_bundle":
        raise MeetingMinutesExtractionError("invalid context bundle artifact_type", reason_code="INVALID_CONTEXT_BUNDLE")

    _gate_checks(transcript, context, gate)

    speaker_turns = transcript.get("speaker_turns")
    segments = context.get("segments")
    if not isinstance(speaker_turns, list):
        raise MeetingMinutesExtractionError("speaker_turns must be a list", reason_code="INVALID_SPEAKER_TURNS")
    if not isinstance(segments, list):
        raise MeetingMinutesExtractionError("segments must be a list", reason_code="INVALID_SEGMENTS")

    attendees = sorted({str(turn.get("speaker")).strip() for turn in speaker_turns if str(turn.get("speaker") or "").strip()})
    meeting_outcomes = _build_outcomes(speaker_turns, segments)
    action_items = _build_action_items(speaker_turns, segments)

    if any(not outcome.get("source_refs") for outcome in meeting_outcomes):
        raise MeetingMinutesExtractionError("each outcome requires source_refs", reason_code="OUTCOME_SOURCE_REFS_REQUIRED")

    coverage = source_coverage({"meeting_outcomes": meeting_outcomes, "action_items": action_items}, transcript_turn_count=len(speaker_turns))

    fingerprint = _short_fingerprint(
        {
            "source_context_bundle_id": context.get("artifact_id"),
            "meeting_outcomes": meeting_outcomes,
            "action_items": action_items,
        }
    )
    artifact_id = f"MMA-{fingerprint}"

    effective_trace_id = trace_id if trace_id is not None else "0" * 32
    effective_span_id = span_id if span_id is not None else "0" * 16
    if not _TRACE_ID_RE.match(effective_trace_id):
        raise MeetingMinutesExtractionError("trace_id must be 32-char lowercase hex", reason_code="INVALID_TRACE_ID")
    if not _SPAN_ID_RE.match(effective_span_id):
        raise MeetingMinutesExtractionError("span_id must be 16-char lowercase hex", reason_code="INVALID_SPAN_ID")

    payload: Dict[str, Any] = {
        "artifact_id": artifact_id,
        "artifact_type": ARTIFACT_TYPE,
        "schema_ref": SCHEMA_REF,
        "schema_version": SCHEMA_VERSION,
        "trace": {"trace_id": effective_trace_id, "span_id": effective_span_id},
        "provenance": {
            "produced_by": PRODUCED_BY,
            "input_artifact_ids": [transcript.get("artifact_id"), context.get("artifact_id"), gate.get("artifact_id")],
            **({"run_id": run_id} if run_id else {}),
        },
        "created_at": _utc_iso(clock),
        "source_context_bundle_id": context.get("artifact_id"),
        "summary": f"Extracted {len(meeting_outcomes)} outcomes and {len(action_items)} action items from explicit markers.",
        "agenda_items": [],
        "meeting_outcomes": meeting_outcomes,
        "action_items": action_items,
        "attendees": attendees,
        "source_coverage": coverage,
    }

    validate_minutes_sources(payload, transcript_artifact=transcript, context_bundle=context)

    grounding_eval = outcome_grounding(payload)
    if grounding_eval["status"] != "pass":
        raise MeetingMinutesExtractionError("outcome grounding eval failed", reason_code="OUTCOME_GROUNDING_FAILED")

    action_eval = action_item_completeness(payload)
    if action_eval["status"] != "pass":
        raise MeetingMinutesExtractionError("action item completeness eval failed", reason_code="ACTION_ITEM_COMPLETENESS_FAILED")

    return payload


def extract_meeting_minutes_via_pqx(
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
    gate_evidence: Mapping[str, Any],
    artifact_store: ArtifactStore,
    *,
    parent_trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    step_name: str = "meeting_minutes_extraction",
) -> Dict[str, Any]:
    """Run meeting minutes extraction through PQX step harness."""
    from spectrum_systems.modules.orchestration.pqx_step_harness import run_pqx_step

    input_ids = [
        transcript_artifact.get("artifact_id") if isinstance(transcript_artifact, Mapping) else None,
        context_bundle.get("artifact_id") if isinstance(context_bundle, Mapping) else None,
        gate_evidence.get("artifact_id") if isinstance(gate_evidence, Mapping) else None,
    ]

    def _execution_fn(inputs: Dict[str, Any], trace_id: str, span_id: str) -> Dict[str, Any]:
        return extract_meeting_minutes(
            inputs["transcript_artifact"],
            inputs["context_bundle"],
            inputs["gate_evidence"],
            trace_id=trace_id,
            span_id=span_id,
            run_id=inputs.get("run_id"),
        )

    return run_pqx_step(
        step_name,
        {
            "transcript_artifact": transcript_artifact,
            "context_bundle": context_bundle,
            "gate_evidence": gate_evidence,
            "input_artifact_ids": [artifact_id for artifact_id in input_ids if artifact_id],
            "run_id": run_id,
        },
        _execution_fn,
        artifact_store,
        parent_trace_id=parent_trace_id,
        expected_output_type=ARTIFACT_TYPE,
    )


__all__ = [
    "MeetingMinutesExtractionError",
    "extract_meeting_minutes",
    "extract_meeting_minutes_via_pqx",
    "PRODUCED_BY",
    "SCHEMA_REF",
    "SCHEMA_VERSION",
    "ARTIFACT_TYPE",
]

"""
MeetingMinutesExtractor — spectrum_systems/modules/transcript_pipeline/meeting_minutes_extractor.py

CPL-04 — Governed, schema-bound, source-grounded meeting minutes extraction.

Inputs:
  * transcript_artifact   (admitted via H08 ingestion)
  * context_bundle        (assembled via CPL-02)
  * gate_evidence         (emitted by CPL-03; must report ``passed_gate``)

Output:
  * meeting_minutes_artifact payload (without ``content_hash``; the PQX harness
    mints it).

Hard rules (CPL-04):
- NO live LLM/API calls in tests. The deterministic extractor is the default.
  A provider_adapter mode exists only as an explicit stub that raises unless a
  test-supplied callable is wired in — no transparent network egress.
- NO routing or release authority. Every claim in the artifact is grounded in
  concrete (source_turn_id, source_segment_id, line_index) references.
- Fail-closed: missing or malformed gate_evidence (failed_gate, missing_gate,
  conditional_gate, missing eval_summary_id, target mismatch) raises
  ``MeetingMinutesExtractionError`` and produces no artifact.
- The pure function returns a payload WITHOUT ``content_hash``. The PQX harness
  owns hash minting and registration.
- No invented decisions or action items: explicit markers are required.
- Unknown assignee / due date are recorded explicitly (assignee_status="unknown"
  / due_date_status="unknown") rather than omitted.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from spectrum_systems.modules.runtime.artifact_store import ArtifactStore

PRODUCED_BY = "meeting_minutes_extractor"
SCHEMA_REF = "transcript_pipeline/meeting_minutes_artifact"
SCHEMA_VERSION = "2.0.0"
ARTIFACT_TYPE = "meeting_minutes_artifact"

EXTRACTION_MODE_DETERMINISTIC = "deterministic"
EXTRACTION_MODE_PROVIDER_ADAPTER = "provider_adapter"
SUPPORTED_EXTRACTION_MODES = (
    EXTRACTION_MODE_DETERMINISTIC,
    EXTRACTION_MODE_PROVIDER_ADAPTER,
)

GATE_STATUS_PASSED = "passed_gate"

_TXA_ID_RE = re.compile(r"^TXA-[A-Z0-9_-]+$")
_CTX_ID_RE = re.compile(r"^CTX-[A-Z0-9_-]+$")
_GTE_ID_RE = re.compile(r"^GTE-[A-Z0-9_-]+$")
_EVS_ID_RE = re.compile(r"^EVS-[A-Z0-9_-]+$")
_TURN_ID_RE = re.compile(r"^T-[0-9]{4,}$")
_SEG_ID_RE = re.compile(r"^SEG-[0-9]{4,}$")
_TRACE_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_SPAN_ID_RE = re.compile(r"^[a-f0-9]{16}$")

# Deterministic extraction parameters. These are bounded constants; nothing in
# the artifact escapes them.
_SUMMARY_TURN_WINDOW = 3
_SUMMARY_MAX_LEN = 480

_DECISION_MARKERS: Tuple[str, ...] = (
    "decision:",
    "we decided",
    "agreed to",
    "agreed that",
)
_ACTION_MARKERS: Tuple[str, ...] = (
    "action:",
    "todo:",
    "will follow up",
    "assigned to",
)
_AGENDA_MARKERS: Tuple[str, ...] = (
    "agenda:",
    "agenda item:",
    "first item",
    "next item",
    "today we are",
    "today we will",
)


class MeetingMinutesExtractionError(RuntimeError):
    """Raised on any deterministic extraction failure. Always carries a reason_code."""

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_iso(clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> str:
    return clock().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _short_fingerprint(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12].upper()


def _derive_artifact_id(
    transcript_id: str,
    context_bundle_id: str,
    gate_evidence_id: str,
    extraction_mode: str,
) -> str:
    fingerprint = _short_fingerprint(
        {
            "transcript_id": transcript_id,
            "context_bundle_id": context_bundle_id,
            "gate_evidence_id": gate_evidence_id,
            "extraction_mode": extraction_mode,
        }
    )
    return f"MMA-{fingerprint}"


# ---------------------------------------------------------------------------
# Input envelope validation
# ---------------------------------------------------------------------------


def _require_mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MeetingMinutesExtractionError(
            f"{label} must be a mapping",
            reason_code=f"INVALID_{label.upper()}_INPUT_TYPE",
        )
    return value


def _validate_envelopes(
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
    gate_evidence: Mapping[str, Any],
) -> Tuple[str, str, str, str]:
    txa_id = transcript_artifact.get("artifact_id")
    ctx_id = context_bundle.get("artifact_id")
    gte_id = gate_evidence.get("artifact_id")
    evs_id = gate_evidence.get("eval_summary_id")

    if transcript_artifact.get("artifact_type") != "transcript_artifact":
        raise MeetingMinutesExtractionError(
            f"Expected transcript_artifact, got {transcript_artifact.get('artifact_type')!r}",
            reason_code="INVALID_TRANSCRIPT_ARTIFACT_TYPE",
            target_artifact_id=str(txa_id) if txa_id is not None else None,
        )
    if context_bundle.get("artifact_type") != "context_bundle":
        raise MeetingMinutesExtractionError(
            f"Expected context_bundle, got {context_bundle.get('artifact_type')!r}",
            reason_code="INVALID_CONTEXT_BUNDLE_ARTIFACT_TYPE",
            target_artifact_id=str(ctx_id) if ctx_id is not None else None,
        )
    if gate_evidence.get("artifact_type") != "gate_evidence":
        raise MeetingMinutesExtractionError(
            f"Expected gate_evidence, got {gate_evidence.get('artifact_type')!r}",
            reason_code="INVALID_GATE_EVIDENCE_ARTIFACT_TYPE",
            target_artifact_id=str(gte_id) if gte_id is not None else None,
        )

    if not isinstance(txa_id, str) or not _TXA_ID_RE.match(txa_id):
        raise MeetingMinutesExtractionError(
            f"transcript_artifact.artifact_id is invalid: {txa_id!r}",
            reason_code="INVALID_TRANSCRIPT_ARTIFACT_ID",
        )
    if not isinstance(ctx_id, str) or not _CTX_ID_RE.match(ctx_id):
        raise MeetingMinutesExtractionError(
            f"context_bundle.artifact_id is invalid: {ctx_id!r}",
            reason_code="INVALID_CONTEXT_BUNDLE_ARTIFACT_ID",
        )
    if not isinstance(gte_id, str) or not _GTE_ID_RE.match(gte_id):
        raise MeetingMinutesExtractionError(
            f"gate_evidence.artifact_id is invalid: {gte_id!r}",
            reason_code="INVALID_GATE_EVIDENCE_ARTIFACT_ID",
        )
    if not isinstance(evs_id, str) or not _EVS_ID_RE.match(evs_id):
        raise MeetingMinutesExtractionError(
            f"gate_evidence.eval_summary_id is missing or invalid: {evs_id!r}",
            reason_code="MISSING_EVAL_SUMMARY_ID",
            target_artifact_id=gte_id,
        )

    if context_bundle.get("source_artifact_id") != txa_id:
        raise MeetingMinutesExtractionError(
            "context_bundle.source_artifact_id does not match transcript_artifact.artifact_id",
            reason_code="BUNDLE_SOURCE_LINK_MISMATCH",
            target_artifact_id=ctx_id,
        )

    return txa_id, ctx_id, gte_id, evs_id


def _validate_gate_evidence(
    gate_evidence: Mapping[str, Any],
    txa_id: str,
    ctx_id: str,
) -> None:
    gate_status = gate_evidence.get("gate_status")
    if gate_status != GATE_STATUS_PASSED:
        raise MeetingMinutesExtractionError(
            f"gate_evidence.gate_status must be 'passed_gate', got {gate_status!r}",
            reason_code="GATE_NOT_PASSED",
            target_artifact_id=gate_evidence.get("artifact_id"),
        )
    target_ids = gate_evidence.get("target_artifact_ids")
    if not isinstance(target_ids, list) or not target_ids:
        raise MeetingMinutesExtractionError(
            "gate_evidence.target_artifact_ids must be a non-empty list",
            reason_code="MISSING_GATE_TARGET_IDS",
            target_artifact_id=gate_evidence.get("artifact_id"),
        )
    target_set = set(target_ids)
    if txa_id not in target_set or ctx_id not in target_set:
        raise MeetingMinutesExtractionError(
            "gate_evidence.target_artifact_ids must include both transcript and context_bundle ids",
            reason_code="GATE_TARGET_MISMATCH",
            target_artifact_id=gate_evidence.get("artifact_id"),
        )


# ---------------------------------------------------------------------------
# Source pair index and segment alignment validation
# ---------------------------------------------------------------------------


def _build_turn_index(transcript: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    speaker_turns = transcript.get("speaker_turns")
    if not isinstance(speaker_turns, list) or not speaker_turns:
        raise MeetingMinutesExtractionError(
            "transcript_artifact.speaker_turns missing or empty",
            reason_code="TRANSCRIPT_TURNS_MISSING",
            target_artifact_id=transcript.get("artifact_id"),
        )
    index: Dict[str, Dict[str, Any]] = {}
    for turn in speaker_turns:
        if not isinstance(turn, Mapping):
            raise MeetingMinutesExtractionError(
                "speaker_turns entry is not a mapping",
                reason_code="TRANSCRIPT_TURN_MALFORMED",
                target_artifact_id=transcript.get("artifact_id"),
            )
        turn_id = turn.get("turn_id")
        if not isinstance(turn_id, str) or not _TURN_ID_RE.match(turn_id):
            raise MeetingMinutesExtractionError(
                f"speaker_turn.turn_id invalid: {turn_id!r}",
                reason_code="TRANSCRIPT_TURN_ID_INVALID",
                target_artifact_id=transcript.get("artifact_id"),
            )
        index[turn_id] = dict(turn)
    return index


def _build_segment_index(bundle: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    segments = bundle.get("segments")
    if not isinstance(segments, list) or not segments:
        raise MeetingMinutesExtractionError(
            "context_bundle.segments missing or empty",
            reason_code="BUNDLE_SEGMENTS_MISSING",
            target_artifact_id=bundle.get("artifact_id"),
        )
    index: Dict[str, Dict[str, Any]] = {}
    for seg in segments:
        if not isinstance(seg, Mapping):
            raise MeetingMinutesExtractionError(
                "context_bundle.segments entry is not a mapping",
                reason_code="BUNDLE_SEGMENT_MALFORMED",
                target_artifact_id=bundle.get("artifact_id"),
            )
        sid = seg.get("segment_id")
        if not isinstance(sid, str) or not _SEG_ID_RE.match(sid):
            raise MeetingMinutesExtractionError(
                f"segment_id invalid: {sid!r}",
                reason_code="BUNDLE_SEGMENT_ID_INVALID",
                target_artifact_id=bundle.get("artifact_id"),
            )
        index[sid] = dict(seg)
    return index


def _validate_segments_align_with_turns(
    bundle: Mapping[str, Any],
    turn_index: Mapping[str, Mapping[str, Any]],
) -> None:
    """Cross-check every bundle segment to a transcript turn by id and line_index.

    Hard rule: the context_bundle was produced from the transcript, so every
    segment must reference an existing turn and carry the same line_index.
    """
    for seg in bundle["segments"]:
        source_turn_id = seg.get("source_turn_id")
        if source_turn_id not in turn_index:
            raise MeetingMinutesExtractionError(
                f"segment {seg.get('segment_id')!r} references missing turn {source_turn_id!r}",
                reason_code="SEGMENT_ORPHAN_TURN",
                target_artifact_id=bundle.get("artifact_id"),
            )
        turn = turn_index[source_turn_id]
        if seg.get("line_index") != turn.get("line_index"):
            raise MeetingMinutesExtractionError(
                f"segment {seg.get('segment_id')!r} line_index drifted from turn {source_turn_id!r}",
                reason_code="SEGMENT_LINE_INDEX_DRIFT",
                target_artifact_id=bundle.get("artifact_id"),
            )


# ---------------------------------------------------------------------------
# Deterministic extraction baseline
# ---------------------------------------------------------------------------


def _make_source_ref(turn: Mapping[str, Any], segment: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "source_turn_id": turn["turn_id"],
        "source_segment_id": segment["segment_id"],
        "line_index": int(turn["line_index"]) if turn.get("line_index") is not None else 0,
    }


def _segments_by_turn(bundle: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return {seg["source_turn_id"]: seg for seg in bundle["segments"]}


def _bounded_summary(turns: Sequence[Mapping[str, Any]]) -> str:
    snippets: List[str] = []
    for turn in turns[:_SUMMARY_TURN_WINDOW]:
        speaker = str(turn.get("speaker", "")).strip()
        text = str(turn.get("text", "")).strip()
        if not speaker or not text:
            continue
        snippets.append(f"{speaker}: {text}")
    summary = " | ".join(snippets) if snippets else "Meeting transcript admitted with no narrative content."
    if len(summary) > _SUMMARY_MAX_LEN:
        summary = summary[: _SUMMARY_MAX_LEN - 3].rstrip() + "..."
    return summary


def _unique_speakers(turns: Sequence[Mapping[str, Any]]) -> List[str]:
    seen: List[str] = []
    seen_set: set[str] = set()
    for turn in turns:
        speaker = str(turn.get("speaker", "")).strip()
        if speaker and speaker not in seen_set:
            seen_set.add(speaker)
            seen.append(speaker)
    return seen


def _text_contains(haystack: str, needles: Sequence[str]) -> bool:
    lowered = haystack.lower()
    return any(needle in lowered for needle in needles)


def _question_text(text: str) -> bool:
    stripped = text.strip()
    return stripped.endswith("?")


def _extract_agenda_items(
    turns: Sequence[Mapping[str, Any]],
    seg_by_turn: Mapping[str, Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    counter = 1
    for turn in turns:
        text = str(turn.get("text", "")).strip()
        if not text:
            continue
        is_marker = _text_contains(text, _AGENDA_MARKERS)
        is_question = _question_text(text)
        if not (is_marker or is_question):
            continue
        seg = seg_by_turn.get(turn["turn_id"])
        if seg is None:
            continue
        items.append(
            {
                "agenda_item_id": f"AGI-{counter:04d}",
                "title": text[:200],
                "source_refs": [_make_source_ref(turn, seg)],
            }
        )
        counter += 1
    return items


def _parse_assignee(text: str) -> Optional[str]:
    """Best-effort, bounded assignee extraction for explicit 'assigned to <name>'.

    Conservative: returns a name only when 'assigned to ' is present in the line
    and the next token group resembles a proper name. No name invention.
    """
    lowered = text.lower()
    marker = "assigned to "
    idx = lowered.find(marker)
    if idx < 0:
        return None
    tail = text[idx + len(marker):].strip()
    if not tail:
        return None
    # Take up to the first sentence-ending punctuation or comma.
    match = re.match(r"([A-Z][A-Za-z0-9 _.\-']{0,63}?)(?:[,.;:!?]|$)", tail)
    if not match:
        return None
    name = match.group(1).strip()
    if not name:
        return None
    return name


def _extract_decisions(
    turns: Sequence[Mapping[str, Any]],
    seg_by_turn: Mapping[str, Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    decisions: List[Dict[str, Any]] = []
    counter = 1
    for turn in turns:
        text = str(turn.get("text", "")).strip()
        if not text or not _text_contains(text, _DECISION_MARKERS):
            continue
        seg = seg_by_turn.get(turn["turn_id"])
        if seg is None:
            continue
        decisions.append(
            {
                "decision_id": f"DEC-{counter:04d}",
                "description": text[:240],
                "source_refs": [_make_source_ref(turn, seg)],
            }
        )
        counter += 1
    return decisions


def _extract_action_items(
    turns: Sequence[Mapping[str, Any]],
    seg_by_turn: Mapping[str, Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    counter = 1
    for turn in turns:
        text = str(turn.get("text", "")).strip()
        if not text or not _text_contains(text, _ACTION_MARKERS):
            continue
        seg = seg_by_turn.get(turn["turn_id"])
        if seg is None:
            continue
        item: Dict[str, Any] = {
            "action_id": f"ACT-{counter:04d}",
            "description": text[:240],
            "source_refs": [_make_source_ref(turn, seg)],
        }
        assignee = _parse_assignee(text)
        if assignee:
            item["assignee"] = assignee
        else:
            item["assignee_status"] = "unknown"
        # Deterministic baseline never invents a due_date.
        item["due_date_status"] = "unknown"
        actions.append(item)
        counter += 1
    return actions


def _compute_source_coverage(
    turns: Sequence[Mapping[str, Any]],
    agenda_items: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
    action_items: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    referenced_turn_ids: set[str] = set()
    referenced_segment_ids: set[str] = set()
    for collection in (agenda_items, decisions, action_items):
        for item in collection:
            for ref in item.get("source_refs", []) or []:
                referenced_turn_ids.add(ref["source_turn_id"])
                referenced_segment_ids.add(ref["source_segment_id"])
    total = len(turns)
    referenced = len(referenced_turn_ids)
    ratio = (referenced / total) if total else 0.0
    return {
        "total_turns": total,
        "referenced_turns": referenced,
        "referenced_segments": len(referenced_segment_ids),
        "coverage_ratio": round(ratio, 6),
    }


# ---------------------------------------------------------------------------
# Public deterministic entrypoint
# ---------------------------------------------------------------------------


def extract_meeting_minutes(
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
    gate_evidence: Mapping[str, Any],
    *,
    extraction_mode: str = EXTRACTION_MODE_DETERMINISTIC,
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    run_id: Optional[str] = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    provider_adapter: Optional[
        Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]
    ] = None,
) -> Dict[str, Any]:
    """Deterministically extract a meeting_minutes_artifact payload.

    Returns
    -------
    A meeting_minutes_artifact payload WITHOUT ``content_hash``. The PQX harness
    mints ``content_hash`` and registers the artifact via the artifact store.

    Raises
    ------
    MeetingMinutesExtractionError
        On any fail-closed condition: invalid envelopes, gate not passed, target
        mismatch, missing eval_summary_id, malformed turns/segments,
        line_index drift, segment-orphan turn, or unsupported extraction_mode.
    """
    if extraction_mode not in SUPPORTED_EXTRACTION_MODES:
        raise MeetingMinutesExtractionError(
            f"Unsupported extraction_mode={extraction_mode!r}",
            reason_code="UNSUPPORTED_EXTRACTION_MODE",
        )

    transcript_artifact = _require_mapping(transcript_artifact, label="transcript")
    context_bundle = _require_mapping(context_bundle, label="context_bundle")
    gate_evidence = _require_mapping(gate_evidence, label="gate_evidence")

    txa_id, ctx_id, gte_id, evs_id = _validate_envelopes(
        transcript_artifact, context_bundle, gate_evidence
    )
    _validate_gate_evidence(gate_evidence, txa_id, ctx_id)

    turn_index = _build_turn_index(transcript_artifact)
    _build_segment_index(context_bundle)
    _validate_segments_align_with_turns(context_bundle, turn_index)

    effective_trace_id = trace_id if trace_id is not None else "0" * 32
    effective_span_id = span_id if span_id is not None else "0" * 16
    if not _TRACE_ID_RE.match(effective_trace_id):
        raise MeetingMinutesExtractionError(
            "trace_id must be a 32-char lowercase hex string",
            reason_code="INVALID_TRACE_ID",
            target_artifact_id=ctx_id,
        )
    if not _SPAN_ID_RE.match(effective_span_id):
        raise MeetingMinutesExtractionError(
            "span_id must be a 16-char lowercase hex string",
            reason_code="INVALID_SPAN_ID",
            target_artifact_id=ctx_id,
        )

    turns: List[Mapping[str, Any]] = transcript_artifact["speaker_turns"]
    seg_by_turn = _segments_by_turn(context_bundle)

    if extraction_mode == EXTRACTION_MODE_DETERMINISTIC:
        agenda_items = _extract_agenda_items(turns, seg_by_turn)
        decisions = _extract_decisions(turns, seg_by_turn)
        action_items = _extract_action_items(turns, seg_by_turn)
        summary = _bounded_summary(turns)
        attendees = _unique_speakers(turns)
    else:
        if provider_adapter is None:
            raise MeetingMinutesExtractionError(
                "provider_adapter mode requires an explicit adapter callable; "
                "no live network egress is performed in this module",
                reason_code="PROVIDER_ADAPTER_UNAVAILABLE",
                target_artifact_id=ctx_id,
            )
        # The provider_adapter, even if supplied, must produce only structures
        # already grounded in (turn, segment) pairs from the inputs above. The
        # caller is responsible for that guarantee; we still validate the
        # output via validate_minutes_source_refs below before returning.
        adapter_payload = provider_adapter(transcript_artifact, context_bundle)
        if not isinstance(adapter_payload, Mapping):
            raise MeetingMinutesExtractionError(
                "provider_adapter returned a non-mapping payload",
                reason_code="PROVIDER_ADAPTER_INVALID_OUTPUT",
                target_artifact_id=ctx_id,
            )
        agenda_items = list(adapter_payload.get("agenda_items", []))
        decisions = list(adapter_payload.get("decisions", []))
        action_items = list(adapter_payload.get("action_items", []))
        summary = str(adapter_payload.get("summary") or _bounded_summary(turns))
        attendees = list(adapter_payload.get("attendees") or _unique_speakers(turns))

    source_coverage = _compute_source_coverage(turns, agenda_items, decisions, action_items)

    artifact_id = _derive_artifact_id(txa_id, ctx_id, gte_id, extraction_mode)
    provenance: Dict[str, Any] = {
        "produced_by": PRODUCED_BY,
        "input_artifact_ids": [txa_id, ctx_id, gte_id, evs_id],
    }
    if run_id:
        provenance["run_id"] = run_id

    payload: Dict[str, Any] = {
        "artifact_id": artifact_id,
        "artifact_type": ARTIFACT_TYPE,
        "schema_ref": SCHEMA_REF,
        "schema_version": SCHEMA_VERSION,
        "trace": {"trace_id": effective_trace_id, "span_id": effective_span_id},
        "provenance": provenance,
        "created_at": _utc_iso(clock),
        "source_artifact_ids": [txa_id, ctx_id],
        "source_context_bundle_id": ctx_id,
        "gate_evidence_id": gte_id,
        "eval_summary_id": evs_id,
        "extraction_mode": extraction_mode,
        "summary": summary,
        "attendees": attendees,
        "agenda_items": agenda_items,
        "decisions": decisions,
        "action_items": action_items,
        "source_coverage": source_coverage,
    }

    # Belt-and-braces validation BEFORE returning. Anything escaping the
    # extractor is fully grounded.
    from spectrum_systems.modules.transcript_pipeline.minutes_source_validation import (
        validate_minutes_source_refs,
    )

    validate_minutes_source_refs(payload, transcript_artifact, context_bundle)

    return payload


# ---------------------------------------------------------------------------
# Governed entrypoint — runs through PQX
# ---------------------------------------------------------------------------


def run_meeting_minutes_extraction_via_pqx(
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
    gate_evidence: Mapping[str, Any],
    artifact_store: ArtifactStore,
    *,
    extraction_mode: str = EXTRACTION_MODE_DETERMINISTIC,
    parent_trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    step_name: str = "meeting_minutes_extraction",
    provider_adapter: Optional[
        Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]
    ] = None,
) -> Dict[str, Any]:
    """Run governed extraction through the PQX step harness.

    The harness owns:
      * trace_id / span_id (or inherits parent_trace_id),
      * content_hash minting,
      * artifact registration in the artifact store,
      * pqx_execution_record emission.

    Returns the harness result dict: ``{"execution_record": ..., "output_artifact": ...}``.
    Raises ``PQXExecutionError`` on any failure (including
    ``MeetingMinutesExtractionError``).
    """
    from spectrum_systems.modules.orchestration.pqx_step_harness import run_pqx_step

    txa_id = transcript_artifact.get("artifact_id") if isinstance(transcript_artifact, Mapping) else None
    ctx_id = context_bundle.get("artifact_id") if isinstance(context_bundle, Mapping) else None
    gte_id = gate_evidence.get("artifact_id") if isinstance(gate_evidence, Mapping) else None
    evs_id = gate_evidence.get("eval_summary_id") if isinstance(gate_evidence, Mapping) else None

    seed_ids: List[str] = [aid for aid in (txa_id, ctx_id, gte_id, evs_id) if isinstance(aid, str)]

    def _execution_fn(inputs: Dict[str, Any], trace_id: str, span_id: str) -> Dict[str, Any]:
        return extract_meeting_minutes(
            inputs["transcript_artifact"],
            inputs["context_bundle"],
            inputs["gate_evidence"],
            extraction_mode=inputs["extraction_mode"],
            trace_id=trace_id,
            span_id=span_id,
            run_id=inputs.get("run_id"),
            provider_adapter=inputs.get("provider_adapter"),
        )

    return run_pqx_step(
        step_name,
        {
            "transcript_artifact": transcript_artifact,
            "context_bundle": context_bundle,
            "gate_evidence": gate_evidence,
            "extraction_mode": extraction_mode,
            "input_artifact_ids": seed_ids,
            "run_id": run_id,
            "provider_adapter": provider_adapter,
        },
        _execution_fn,
        artifact_store,
        parent_trace_id=parent_trace_id,
        expected_output_type=ARTIFACT_TYPE,
    )


__all__ = [
    "MeetingMinutesExtractionError",
    "extract_meeting_minutes",
    "run_meeting_minutes_extraction_via_pqx",
    "PRODUCED_BY",
    "SCHEMA_REF",
    "SCHEMA_VERSION",
    "ARTIFACT_TYPE",
    "EXTRACTION_MODE_DETERMINISTIC",
    "EXTRACTION_MODE_PROVIDER_ADAPTER",
    "SUPPORTED_EXTRACTION_MODES",
]

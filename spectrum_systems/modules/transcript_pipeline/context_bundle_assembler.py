"""
ContextBundleAssembler — spectrum_systems/modules/transcript_pipeline/context_bundle_assembler.py

CPL-02 — Deterministic, governed context bundle assembly.

Consumes a ``transcript_artifact`` payload (already admitted by H08) and produces
a ``context_bundle`` payload that is:

- deterministic and replayable: same transcript_artifact => identical segments,
  identical ordering, identical ``manifest_hash``, identical ``content_hash``.
- fully traceable: every segment carries ``source_turn_id`` + ``line_index``
  pointing back to a real ``speaker_turns`` entry on the source transcript.
- fail-closed: missing source linkage, malformed input, duplicate segment ids,
  or orphan turns raise ``ContextBundleAssemblyError`` with a structured
  ``reason_code``. No artifact is produced on failure.

Hard rules (CPL-02):
- NO LLM calls. NO summarization. NO routing.
- The assembler does NOT write to the artifact store. The PQX harness owns
  registration. Use ``assemble_context_bundle_via_pqx`` for the governed path.
- ``content_hash`` is computed by the artifact store / PQX harness; this module
  computes ``manifest_hash`` only (a separate, segment-only deterministic
  fingerprint independent of envelope metadata).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional

from spectrum_systems.modules.runtime.artifact_store import ArtifactStore

PRODUCED_BY = "context_bundle_assembler"
SCHEMA_REF = "transcript_pipeline/context_bundle"
SCHEMA_VERSION = "1.0.0"
ARTIFACT_TYPE = "context_bundle"
ASSEMBLY_STRATEGY = "full"

_TURN_ID_RE = re.compile(r"^T-[0-9]{4,}$")
_TXA_ID_RE = re.compile(r"^TXA-[A-Z0-9_-]+$")
_TRACE_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_SPAN_ID_RE = re.compile(r"^[a-f0-9]{16}$")


class ContextBundleAssemblyError(RuntimeError):
    """Raised on any deterministic assembly failure. Always carries a reason_code."""

    def __init__(
        self,
        message: str,
        reason_code: str,
        source_artifact_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.source_artifact_id = source_artifact_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "reason_code": self.reason_code,
            "source_artifact_id": self.source_artifact_id,
        }


def _validate_transcript_envelope(transcript_artifact: Mapping[str, Any]) -> str:
    """Validate the transcript_artifact envelope and return its artifact_id.

    Raises ContextBundleAssemblyError on any structural violation.
    """
    if not isinstance(transcript_artifact, Mapping):
        raise ContextBundleAssemblyError(
            "transcript_artifact must be a mapping",
            reason_code="INVALID_INPUT_TYPE",
        )

    artifact_type = transcript_artifact.get("artifact_type")
    if artifact_type != "transcript_artifact":
        raise ContextBundleAssemblyError(
            f"Expected artifact_type='transcript_artifact', got {artifact_type!r}",
            reason_code="INVALID_SOURCE_ARTIFACT_TYPE",
            source_artifact_id=transcript_artifact.get("artifact_id"),
        )

    source_artifact_id = transcript_artifact.get("artifact_id")
    if not isinstance(source_artifact_id, str) or not _TXA_ID_RE.match(source_artifact_id):
        raise ContextBundleAssemblyError(
            f"Source transcript_artifact has invalid artifact_id: {source_artifact_id!r}",
            reason_code="INVALID_SOURCE_ARTIFACT_ID",
            source_artifact_id=str(source_artifact_id) if source_artifact_id is not None else None,
        )

    if "speaker_turns" not in transcript_artifact:
        raise ContextBundleAssemblyError(
            "transcript_artifact missing 'speaker_turns'",
            reason_code="MISSING_SPEAKER_TURNS",
            source_artifact_id=source_artifact_id,
        )

    return source_artifact_id


def _validate_speaker_turns(
    speaker_turns: Any, *, source_artifact_id: str
) -> List[Dict[str, Any]]:
    """Validate the structure of speaker_turns and return a list copy.

    Every turn must have a non-empty ``turn_id``, ``speaker``, ``text``, and a
    non-negative integer ``line_index``. Duplicate turn_ids are rejected.
    """
    if not isinstance(speaker_turns, list):
        raise ContextBundleAssemblyError(
            "transcript_artifact.speaker_turns must be a list",
            reason_code="INVALID_SPEAKER_TURNS_TYPE",
            source_artifact_id=source_artifact_id,
        )
    if not speaker_turns:
        raise ContextBundleAssemblyError(
            "transcript_artifact.speaker_turns is empty",
            reason_code="EMPTY_SPEAKER_TURNS",
            source_artifact_id=source_artifact_id,
        )

    seen_turn_ids: Dict[str, int] = {}
    cleaned: List[Dict[str, Any]] = []
    for idx, turn in enumerate(speaker_turns):
        if not isinstance(turn, Mapping):
            raise ContextBundleAssemblyError(
                f"speaker_turns[{idx}] is not a mapping",
                reason_code="INVALID_TURN_TYPE",
                source_artifact_id=source_artifact_id,
            )
        turn_id = turn.get("turn_id")
        speaker = turn.get("speaker")
        text = turn.get("text")
        line_index = turn.get("line_index", 0)

        if not isinstance(turn_id, str) or not _TURN_ID_RE.match(turn_id):
            raise ContextBundleAssemblyError(
                f"speaker_turns[{idx}].turn_id is invalid: {turn_id!r}",
                reason_code="INVALID_TURN_ID",
                source_artifact_id=source_artifact_id,
            )
        if turn_id in seen_turn_ids:
            raise ContextBundleAssemblyError(
                f"Duplicate turn_id in transcript: {turn_id!r}",
                reason_code="DUPLICATE_TURN_ID",
                source_artifact_id=source_artifact_id,
            )
        if not isinstance(speaker, str) or not speaker.strip():
            raise ContextBundleAssemblyError(
                f"speaker_turns[{idx}].speaker is empty or non-string",
                reason_code="INVALID_TURN_SPEAKER",
                source_artifact_id=source_artifact_id,
            )
        if not isinstance(text, str) or not text.strip():
            raise ContextBundleAssemblyError(
                f"speaker_turns[{idx}].text is empty or non-string",
                reason_code="INVALID_TURN_TEXT",
                source_artifact_id=source_artifact_id,
            )
        if not isinstance(line_index, int) or isinstance(line_index, bool) or line_index < 0:
            raise ContextBundleAssemblyError(
                f"speaker_turns[{idx}].line_index must be a non-negative int",
                reason_code="INVALID_TURN_LINE_INDEX",
                source_artifact_id=source_artifact_id,
            )

        seen_turn_ids[turn_id] = idx
        cleaned.append(
            {
                "turn_id": turn_id,
                "speaker": speaker,
                "text": text,
                "line_index": line_index,
            }
        )

    return cleaned


def _build_segments(turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Project validated speaker_turns into ordered segments (1:1, no loss)."""
    segments: List[Dict[str, Any]] = []
    seen_segment_ids: set[str] = set()
    for idx, turn in enumerate(turns):
        segment_id = f"SEG-{idx + 1:04d}"
        if segment_id in seen_segment_ids:
            raise ContextBundleAssemblyError(
                f"Duplicate segment_id generated: {segment_id}",
                reason_code="DUPLICATE_SEGMENT_ID",
            )
        seen_segment_ids.add(segment_id)
        segments.append(
            {
                "segment_id": segment_id,
                "speaker": turn["speaker"],
                "text": turn["text"],
                "source_turn_id": turn["turn_id"],
                "line_index": turn["line_index"],
            }
        )
    return segments


def _enforce_referential_integrity(
    segments: List[Dict[str, Any]],
    turns: List[Dict[str, Any]],
    *,
    source_artifact_id: str,
) -> None:
    """Verify every segment maps to a real turn, no orphans, no duplicates."""
    if len(segments) != len(turns):
        raise ContextBundleAssemblyError(
            f"Segment count {len(segments)} does not match turn count {len(turns)}",
            reason_code="SEGMENT_TURN_COUNT_MISMATCH",
            source_artifact_id=source_artifact_id,
        )

    valid_turn_ids = {turn["turn_id"] for turn in turns}
    seen_segment_ids: set[str] = set()
    for idx, segment in enumerate(segments):
        sid = segment["segment_id"]
        if sid in seen_segment_ids:
            raise ContextBundleAssemblyError(
                f"Duplicate segment_id: {sid}",
                reason_code="DUPLICATE_SEGMENT_ID",
                source_artifact_id=source_artifact_id,
            )
        seen_segment_ids.add(sid)
        if segment["source_turn_id"] not in valid_turn_ids:
            raise ContextBundleAssemblyError(
                f"Segment {sid} references missing turn {segment['source_turn_id']!r}",
                reason_code="ORPHAN_SEGMENT",
                source_artifact_id=source_artifact_id,
            )
        # Strict 1:1 ordering: segment[i] must align to turn[i].
        expected_turn = turns[idx]
        if (
            segment["source_turn_id"] != expected_turn["turn_id"]
            or segment["speaker"] != expected_turn["speaker"]
            or segment["text"] != expected_turn["text"]
            or segment["line_index"] != expected_turn["line_index"]
        ):
            raise ContextBundleAssemblyError(
                f"Segment {sid} drifted from source turn {expected_turn['turn_id']!r}",
                reason_code="SEGMENT_TURN_DRIFT",
                source_artifact_id=source_artifact_id,
            )


def _compute_manifest_hash(segments: List[Dict[str, Any]]) -> str:
    """Deterministic hash over the ordered segment manifest only.

    Excludes envelope, trace, created_at, content_hash, provenance, etc.
    Same segment list (same content, same order) => same manifest_hash.
    """
    canonical = json.dumps(
        segments,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _derive_artifact_id(source_artifact_id: str, manifest_hash: str) -> str:
    """Deterministic context bundle id derived from source + manifest.

    CTX-<TXA-suffix>-<manifest12>. Same inputs => identical id.
    """
    txa_suffix = source_artifact_id.split("-", 1)[1] if "-" in source_artifact_id else source_artifact_id
    manifest_suffix = manifest_hash.split(":", 1)[1][:12].upper()
    return f"CTX-{txa_suffix}-{manifest_suffix}"


def _utc_iso(clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> str:
    return clock().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def assemble_context_bundle(
    transcript_artifact: Mapping[str, Any],
    *,
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    run_id: Optional[str] = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> Dict[str, Any]:
    """Deterministically assemble a ``context_bundle`` payload from a transcript.

    Parameters
    ----------
    transcript_artifact:
        A validated ``transcript_artifact`` payload (as produced by H08 / the
        artifact store). Must contain ``speaker_turns``.
    trace_id, span_id:
        Provided by the PQX harness when called via ``assemble_context_bundle_via_pqx``.
        When called directly (e.g., for testing the pure projection), default
        values of zero-bytes are used and the caller must replace them or run
        the function through PQX.
    run_id:
        Optional governed run id, copied into provenance.
    clock:
        Injectable clock for deterministic tests.

    Returns
    -------
    A complete context_bundle payload (without ``content_hash``; the PQX harness
    / artifact store computes that).

    Raises
    ------
    ContextBundleAssemblyError
        On any fail-closed condition: missing source linkage, orphan segments,
        empty / malformed turns, duplicate ids.
    """
    source_artifact_id = _validate_transcript_envelope(transcript_artifact)
    turns = _validate_speaker_turns(
        transcript_artifact.get("speaker_turns"),
        source_artifact_id=source_artifact_id,
    )
    segments = _build_segments(turns)
    _enforce_referential_integrity(segments, turns, source_artifact_id=source_artifact_id)

    manifest_hash = _compute_manifest_hash(segments)
    artifact_id = _derive_artifact_id(source_artifact_id, manifest_hash)

    effective_trace_id = trace_id if trace_id is not None else "0" * 32
    effective_span_id = span_id if span_id is not None else "0" * 16
    if not _TRACE_ID_RE.match(effective_trace_id):
        raise ContextBundleAssemblyError(
            "trace_id must be a 32-char lowercase hex string",
            reason_code="INVALID_TRACE_ID",
            source_artifact_id=source_artifact_id,
        )
    if not _SPAN_ID_RE.match(effective_span_id):
        raise ContextBundleAssemblyError(
            "span_id must be a 16-char lowercase hex string",
            reason_code="INVALID_SPAN_ID",
            source_artifact_id=source_artifact_id,
        )

    provenance: Dict[str, Any] = {
        "produced_by": PRODUCED_BY,
        "input_artifact_ids": [source_artifact_id],
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
        "source_artifact_id": source_artifact_id,
        "segments": segments,
        "manifest_hash": manifest_hash,
        "assembly_strategy": ASSEMBLY_STRATEGY,
    }
    return payload


def assemble_context_bundle_via_pqx(
    transcript_artifact: Mapping[str, Any],
    artifact_store: ArtifactStore,
    *,
    parent_trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    step_name: str = "context_bundle_assembly",
) -> Dict[str, Any]:
    """Run context bundle assembly through the PQX step harness.

    This is the only sanctioned entrypoint for producing a context_bundle in
    the governed runtime. The harness:
      * supplies trace_id / span_id (or inherits parent_trace_id),
      * computes content_hash,
      * registers the artifact in the artifact store,
      * emits a pqx_execution_record.

    Returns the harness result dict: ``{"execution_record": ..., "output_artifact": ...}``.
    Raises ``PQXExecutionError`` on any failure (including ContextBundleAssemblyError).
    """
    from spectrum_systems.modules.orchestration.pqx_step_harness import run_pqx_step

    source_artifact_id = transcript_artifact.get("artifact_id") if isinstance(transcript_artifact, Mapping) else None

    def _execution_fn(inputs: Dict[str, Any], trace_id: str, span_id: str) -> Dict[str, Any]:
        return assemble_context_bundle(
            inputs["transcript_artifact"],
            trace_id=trace_id,
            span_id=span_id,
            run_id=inputs.get("run_id"),
        )

    return run_pqx_step(
        step_name,
        {
            "transcript_artifact": transcript_artifact,
            "input_artifact_ids": [source_artifact_id] if source_artifact_id else [],
            "run_id": run_id,
        },
        _execution_fn,
        artifact_store,
        parent_trace_id=parent_trace_id,
        expected_output_type=ARTIFACT_TYPE,
    )


__all__ = [
    "ContextBundleAssemblyError",
    "assemble_context_bundle",
    "assemble_context_bundle_via_pqx",
    "PRODUCED_BY",
    "SCHEMA_REF",
    "SCHEMA_VERSION",
    "ARTIFACT_TYPE",
    "ASSEMBLY_STRATEGY",
]

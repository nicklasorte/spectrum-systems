"""
TranscriptIngestor — spectrum_systems/modules/transcript_pipeline/transcript_ingestor.py

H08 — MVP-1 Transcript Ingestion (Governed, Fail-Closed).

Deterministically converts raw transcript files into transcript_artifact payloads
that are admitted ONLY through the PQX harness and ONLY written via the artifact
store.

Hard rules:
- No LLM calls.
- No direct artifact writes (caller MUST go through ``ingest_transcript_via_pqx``
  or pass the parsed payload to ``run_pqx_step``).
- Fail-closed on bad input. Empty / unstructured / non-text / oversized inputs
  raise ``TranscriptIngestionError`` with a structured ``reason_code``.
- No free-text outside the schema. Every output field is bounded.
- Determinism: identical input file => identical payload (modulo ``trace`` and
  ``created_at``, which are excluded from ``content_hash``).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from spectrum_systems.modules.runtime.artifact_store import ArtifactStore

PRODUCED_BY = "transcript_ingestor"
SCHEMA_REF = "transcript_pipeline/transcript_artifact"
SCHEMA_VERSION = "1.0.0"
ARTIFACT_TYPE = "transcript_artifact"

_MAX_INPUT_BYTES = 5 * 1024 * 1024  # 5 MiB
_SPEAKER_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9 _\-\.']{0,63}):\s*(.+?)\s*$")
_VALID_SOURCE_FORMATS = frozenset(["txt", "vtt", "srt", "json", "docx"])


class TranscriptIngestionError(RuntimeError):
    """Raised on any deterministic ingestion failure. Always carries a reason_code."""

    def __init__(self, message: str, reason_code: str, file_path: Optional[str] = None) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.file_path = file_path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "reason_code": self.reason_code,
            "file_path": self.file_path,
        }


def _read_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.is_file():
        raise TranscriptIngestionError(
            f"Transcript file not found: {file_path}",
            reason_code="INPUT_FILE_NOT_FOUND",
            file_path=file_path,
        )
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise TranscriptIngestionError(
            f"Cannot stat transcript file: {exc}",
            reason_code="INPUT_FILE_UNREADABLE",
            file_path=file_path,
        ) from exc
    if size > _MAX_INPUT_BYTES:
        raise TranscriptIngestionError(
            f"Transcript file exceeds size limit ({size} > {_MAX_INPUT_BYTES} bytes)",
            reason_code="INPUT_FILE_TOO_LARGE",
            file_path=file_path,
        )
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise TranscriptIngestionError(
            f"Transcript file is not valid UTF-8: {exc}",
            reason_code="INPUT_NOT_UTF8",
            file_path=file_path,
        ) from exc


def _derive_session_id(file_path: str, raw_text: str) -> str:
    """Deterministic session id from path + content."""
    h = hashlib.sha256()
    h.update(Path(file_path).name.encode("utf-8"))
    h.update(b"\x00")
    h.update(raw_text.encode("utf-8"))
    digest = h.hexdigest()[:16].upper()
    return f"SES-{digest}"


def _derive_artifact_id(session_id: str) -> str:
    suffix = session_id.split("-", 1)[1] if "-" in session_id else session_id
    return f"TXA-{suffix}"


def parse_transcript_text(raw_text: str) -> List[Dict[str, Any]]:
    """Parse raw transcript text into ordered speaker turns.

    Deterministic. Same input => identical output (turn_id, speaker, text, line_index).

    Raises TranscriptIngestionError on:
      * empty / whitespace-only input            -> EMPTY_TRANSCRIPT
      * non-string input                         -> INVALID_INPUT_TYPE
      * no parseable ``Speaker: text`` lines     -> NO_SPEAKER_TURNS
    """
    if not isinstance(raw_text, str):
        raise TranscriptIngestionError(
            "raw_text must be a string",
            reason_code="INVALID_INPUT_TYPE",
        )
    if not raw_text or not raw_text.strip():
        raise TranscriptIngestionError(
            "Transcript is empty or whitespace-only",
            reason_code="EMPTY_TRANSCRIPT",
        )

    turns: List[Dict[str, Any]] = []
    for idx, raw_line in enumerate(raw_text.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        match = _SPEAKER_LINE.match(line)
        if not match:
            continue
        speaker = match.group(1).strip()
        text = match.group(2).strip()
        if not speaker or not text:
            continue
        turn_id = f"T-{len(turns) + 1:04d}"
        turns.append(
            {
                "turn_id": turn_id,
                "speaker": speaker,
                "text": text,
                "line_index": idx,
            }
        )

    if not turns:
        raise TranscriptIngestionError(
            "No parseable 'Speaker: text' turns found in transcript",
            reason_code="NO_SPEAKER_TURNS",
        )

    return turns


def _build_payload(
    *,
    file_path: str,
    raw_text: str,
    speaker_turns: List[Dict[str, Any]],
    trace_id: str,
    span_id: str,
    input_artifact_ids: List[str],
    run_id: Optional[str],
    created_at: str,
    source_format: str,
) -> Dict[str, Any]:
    session_id = _derive_session_id(file_path, raw_text)
    artifact_id = _derive_artifact_id(session_id)
    speakers = sorted({turn["speaker"] for turn in speaker_turns})

    provenance: Dict[str, Any] = {
        "produced_by": PRODUCED_BY,
        "input_artifact_ids": list(input_artifact_ids),
    }
    if run_id:
        provenance["run_id"] = run_id

    payload: Dict[str, Any] = {
        "artifact_id": artifact_id,
        "artifact_type": ARTIFACT_TYPE,
        "schema_ref": SCHEMA_REF,
        "schema_version": SCHEMA_VERSION,
        "trace": {"trace_id": trace_id, "span_id": span_id},
        "provenance": provenance,
        "created_at": created_at,
        "source_format": source_format,
        "raw_text": raw_text,
        "session_id": session_id,
        "speaker_turns": speaker_turns,
        "speaker_count": len(speakers),
    }
    return payload


def _utc_iso(clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> str:
    return clock().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ingest_transcript(
    file_path: str,
    *,
    trace_id: str,
    span_id: str,
    input_artifact_ids: Optional[List[str]] = None,
    run_id: Optional[str] = None,
    source_format: str = "txt",
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> Dict[str, Any]:
    """Deterministically build a transcript_artifact payload from a file.

    This function returns a payload only. It does NOT write to the artifact store
    and does NOT compute ``content_hash`` — both are owned by the artifact store
    and the PQX harness respectively.

    Parameters
    ----------
    file_path:
        Absolute or repo-relative path to a UTF-8 transcript file.
    trace_id, span_id:
        Required by the governed runtime; the PQX harness supplies these.
    input_artifact_ids:
        Upstream artifact ids in provenance. Defaults to [].
    run_id:
        Optional governed run id.
    source_format:
        Must be one of ``txt|vtt|srt|json|docx``.

    Raises
    ------
    TranscriptIngestionError
        On any deterministic failure. Each error has a ``reason_code``.
    """
    if not isinstance(file_path, str) or not file_path:
        raise TranscriptIngestionError(
            "file_path must be a non-empty string",
            reason_code="INVALID_FILE_PATH",
        )
    if source_format not in _VALID_SOURCE_FORMATS:
        raise TranscriptIngestionError(
            f"Unsupported source_format: {source_format!r}",
            reason_code="INVALID_SOURCE_FORMAT",
            file_path=file_path,
        )
    if not isinstance(trace_id, str) or not re.fullmatch(r"[a-f0-9]{32}", trace_id):
        raise TranscriptIngestionError(
            "trace_id must be a 32-char lowercase hex string",
            reason_code="INVALID_TRACE_ID",
            file_path=file_path,
        )
    if not isinstance(span_id, str) or not re.fullmatch(r"[a-f0-9]{16}", span_id):
        raise TranscriptIngestionError(
            "span_id must be a 16-char lowercase hex string",
            reason_code="INVALID_SPAN_ID",
            file_path=file_path,
        )

    raw_text = _read_text(file_path)
    speaker_turns = parse_transcript_text(raw_text)

    return _build_payload(
        file_path=file_path,
        raw_text=raw_text,
        speaker_turns=speaker_turns,
        trace_id=trace_id,
        span_id=span_id,
        input_artifact_ids=list(input_artifact_ids or []),
        run_id=run_id,
        created_at=_utc_iso(clock),
        source_format=source_format,
    )


def ingest_transcript_via_pqx(
    file_path: str,
    artifact_store: ArtifactStore,
    *,
    parent_trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    source_format: str = "txt",
    step_name: str = "transcript_ingestion",
) -> Dict[str, Any]:
    """Run transcript ingestion through the PQX step harness.

    This is the only sanctioned entrypoint for producing a transcript_artifact
    in the governed runtime. The harness:
      * generates trace_id / span_id (or inherits parent_trace_id),
      * computes content_hash,
      * registers the artifact in the artifact store,
      * emits a pqx_execution_record (success or failure).

    Returns the harness result dict: ``{"execution_record": ..., "output_artifact": ...}``.
    Raises ``PQXExecutionError`` on any failure (including TranscriptIngestionError).
    """
    from spectrum_systems.modules.orchestration.pqx_step_harness import run_pqx_step

    def _execution_fn(inputs: Dict[str, Any], trace_id: str, span_id: str) -> Dict[str, Any]:
        return ingest_transcript(
            inputs["file_path"],
            trace_id=trace_id,
            span_id=span_id,
            input_artifact_ids=inputs.get("input_artifact_ids", []),
            run_id=inputs.get("run_id"),
            source_format=inputs.get("source_format", "txt"),
        )

    return run_pqx_step(
        step_name,
        {
            "file_path": file_path,
            "input_artifact_ids": [],
            "run_id": run_id,
            "source_format": source_format,
        },
        _execution_fn,
        artifact_store,
        parent_trace_id=parent_trace_id,
        expected_output_type=ARTIFACT_TYPE,
    )


__all__ = [
    "TranscriptIngestionError",
    "ingest_transcript",
    "ingest_transcript_via_pqx",
    "parse_transcript_text",
    "PRODUCED_BY",
    "SCHEMA_REF",
    "ARTIFACT_TYPE",
]

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Sequence

from spectrum_systems.contracts import validate_artifact


class TranscriptHardeningError(Exception):
    """Raised when transcript-domain processing cannot continue."""


TRANSCRIPT_RUN_SCHEMA_VERSION = "1.0.0"
TRANSCRIPT_NORMALIZER_VERSION = "trn-normalizer-1.0.0"
EVIDENCE_PREPARATION_VERSION = "trn-evidence-1.0.0"


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _segment_sort_key(segment: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(segment.get("timestamp") or ""), str(segment.get("segment_id") or ""), str(segment.get("text") or ""))


def normalize_transcript_segments(transcript_payload: Mapping[str, Any], *, chunk_size: int = 2) -> Dict[str, Any]:
    raw_segments = transcript_payload.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise TranscriptHardeningError("transcript requires non-empty segments")

    normalized: List[Dict[str, Any]] = []
    for index, raw in enumerate(raw_segments, start=1):
        if not isinstance(raw, Mapping):
            raise TranscriptHardeningError("segment must be an object")
        segment = {
            "segment_id": _clean_text(raw.get("segment_id") or f"seg-{index:04d}"),
            "speaker": _clean_text(raw.get("speaker") or "unknown-speaker"),
            "text": _clean_text(raw.get("text")),
            "timestamp": _clean_text(raw.get("timestamp")),
            "ordinal": index,
        }
        if not segment["text"]:
            raise TranscriptHardeningError(f"segment text missing at index {index}")
        normalized.append(segment)

    ordered = sorted(normalized, key=_segment_sort_key)
    chunks = [ordered[i : i + chunk_size] for i in range(0, len(ordered), chunk_size)]
    return {
        "segment_count": len(ordered),
        "segments": ordered,
        "replay_hash": _stable_hash(ordered),
        "chunking": {
            "chunk_size": chunk_size,
            "chunk_count": len(chunks),
            "chunk_hashes": [_stable_hash(chunk) for chunk in chunks],
        },
    }


def _anchor_for_text(text: str, segments: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    lowered = text.lower()
    for segment in segments:
        source = str(segment.get("text") or "")
        source_lower = source.lower()
        if lowered in source_lower:
            start = source_lower.index(lowered)
            return {
                "segment_id": str(segment["segment_id"]),
                "start_char": start,
                "end_char": start + len(text),
                "timestamp": str(segment.get("timestamp") or ""),
            }
    raise TranscriptHardeningError(f"cannot anchor text to transcript evidence: {text}")


def build_transcript_observations(segments: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    topics: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    ambiguities: list[dict[str, Any]] = []

    for segment in segments:
        text = str(segment["text"])
        lowered = text.lower()
        anchor = _anchor_for_text(text, segments)
        row = {"text": text, "evidence": [anchor]}

        if any(token in lowered for token in ("topic", "agenda", "focus")):
            topics.append(row)
        if any(token in lowered for token in ("claim", "because", "indicates", "shows")):
            claims.append(row)
        if any(token in lowered for token in ("action", "will", "follow up", "todo")):
            actions.append(row)
        if "?" in text:
            ambiguities.append(row)

    return {
        "topics": topics,
        "claims": claims,
        "actions": actions,
        "ambiguities": ambiguities,
        "evidence_anchor_count": sum(len(group) for group in (topics, claims, actions, ambiguities)),
    }


def build_owner_handoffs(*, trace_id: str, run_id: str, transcript_run_ref: str, replay_hash: str) -> Dict[str, Any]:
    return {
        "eval_input": {
            "artifact_type": "transcript_eval_input_signal",
            "trace_id": trace_id,
            "run_id": run_id,
            "transcript_run_ref": transcript_run_ref,
            "replay_hash": replay_hash,
        },
        "control_input": {
            "artifact_type": "transcript_control_input_signal",
            "trace_id": trace_id,
            "run_id": run_id,
            "transcript_run_ref": transcript_run_ref,
        },
        "judgment_input": {
            "artifact_type": "transcript_judgment_input_signal",
            "trace_id": trace_id,
            "run_id": run_id,
            "transcript_run_ref": transcript_run_ref,
        },
        "certification_input": {
            "artifact_type": "transcript_certification_input_signal",
            "trace_id": trace_id,
            "run_id": run_id,
            "transcript_run_ref": transcript_run_ref,
        },
    }


def run_transcript_hardening(
    transcript_payload: Mapping[str, Any], *, trace_id: str, run_id: str, now: datetime | None = None
) -> Dict[str, Any]:
    generated_at = (now or datetime.now(timezone.utc)).isoformat()
    normalization = normalize_transcript_segments(transcript_payload)
    observations = build_transcript_observations(normalization["segments"])

    artifact_id = f"trn-run-{_stable_hash([trace_id, run_id, normalization['replay_hash']])[:16]}"
    handoff = build_owner_handoffs(
        trace_id=trace_id,
        run_id=run_id,
        transcript_run_ref=artifact_id,
        replay_hash=normalization["replay_hash"],
    )

    artifact = {
        "artifact_type": "transcript_hardening_run",
        "schema_version": TRANSCRIPT_RUN_SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "generated_at": generated_at,
        "source_refs": [str(item) for item in transcript_payload.get("source_refs", []) if str(item).strip()],
        "processor_versions": {
            "normalizer": TRANSCRIPT_NORMALIZER_VERSION,
            "evidence_preparation": EVIDENCE_PREPARATION_VERSION,
        },
        "normalization": normalization,
        "observations": observations,
        "handoff_artifacts": handoff,
        "lineage": {
            "input_hash": _stable_hash(transcript_payload),
            "output_hash": _stable_hash({"normalization": normalization, "observations": observations}),
            "replay_hash": normalization["replay_hash"],
        },
        "processing_status": "processed",
    }
    validate_artifact(artifact, "transcript_hardening_run")
    return artifact

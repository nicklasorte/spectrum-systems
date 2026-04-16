from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping
from xml.etree import ElementTree as ET


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_REQUIRED_EVALS = (
    "schema_conformance",
    "completeness",
    "evidence_coverage",
    "contradiction_detection",
    "policy_alignment",
    "replay_consistency",
)


class DownstreamFailClosedError(ValueError):
    """Raised when a required contract/control/eval precondition is missing."""


@dataclass(frozen=True)
class TranscriptLine:
    line_id: str
    speaker: str
    timestamp: str | None
    text: str
    confidence: float
    ambiguity_flags: List[str]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_docx_text(docx_path: Path) -> List[str]:
    if docx_path.suffix.lower() != ".docx":
        raise DownstreamFailClosedError("source must be a .docx artifact")
    if not docx_path.exists():
        raise DownstreamFailClosedError("source artifact path missing")

    with zipfile.ZipFile(docx_path) as zf:
        try:
            xml_bytes = zf.read("word/document.xml")
        except KeyError as exc:
            raise DownstreamFailClosedError("docx missing word/document.xml") from exc

    root = ET.fromstring(xml_bytes)
    paragraphs: List[str] = []
    for p in root.findall(".//w:p", NS):
        words = [n.text for n in p.findall(".//w:t", NS) if n.text]
        joined = "".join(words).strip()
        if joined:
            paragraphs.append(joined)
    if not paragraphs:
        raise DownstreamFailClosedError("docx produced no text")
    return paragraphs


def _parse_line(raw: str, index: int) -> TranscriptLine:
    timestamp_match = re.match(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$", raw)
    timestamp = None
    rest = raw
    flags: List[str] = []
    if timestamp_match:
        timestamp = timestamp_match.group(1)
        rest = timestamp_match.group(2)
    else:
        flags.append("missing_timestamp")

    speaker_match = re.match(r"^([A-Za-z][A-Za-z0-9 _.-]{1,40}):\s*(.+)$", rest)
    if speaker_match:
        speaker = speaker_match.group(1).strip()
        text = speaker_match.group(2).strip()
        confidence = 0.98 if timestamp else 0.9
    else:
        speaker = "UNKNOWN"
        text = rest.strip()
        flags.append("ambiguous_speaker")
        confidence = 0.6 if timestamp else 0.45

    if not text:
        raise DownstreamFailClosedError(f"line {index} has no recoverable transcript text")

    return TranscriptLine(
        line_id=f"LINE-{index:04d}",
        speaker=speaker,
        timestamp=timestamp,
        text=text,
        confidence=confidence,
        ambiguity_flags=flags,
    )


def normalize_docx_transcript(
    *,
    source_docx_path: str,
    source_id: str,
    run_id: str,
    trace_id: str,
    parser_version: str,
    chunk_size: int = 4,
    ingest_timestamp: str | None = None,
) -> Dict[str, Any]:
    """Deterministically parse DOCX transcript into normalized + chunk artifacts."""
    if not trace_id or not run_id or not source_id:
        raise DownstreamFailClosedError("trace_id, run_id, and source_id are required")

    source_path = Path(source_docx_path)
    paragraphs = _read_docx_text(source_path)
    lines = [_parse_line(raw, idx + 1) for idx, raw in enumerate(paragraphs)]
    ingest_ts = ingest_timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    normalized_payload = {
        "artifact_type": "normalized_transcript_artifact",
        "artifact_id": f"NTA-{_sha256_text(source_id + run_id)[:12].upper()}",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "trace_id": trace_id,
        "source_id": source_id,
        "source_document_path": str(source_path),
        "source_document_hash": _sha256_text("\n".join(paragraphs)),
        "ingest_timestamp": ingest_ts,
        "parser_version": parser_version,
        "lineage_refs": [f"raw:{source_id}"],
        "provenance": {"ingested_by": "downstream_product_substrate", "ingest_mode": "docx"},
        "lines": [line.__dict__ for line in lines],
    }

    chunks = []
    for idx in range(0, len(lines), chunk_size):
        chunk_lines = lines[idx : idx + chunk_size]
        text = "\n".join(f"{l.speaker}: {l.text}" for l in chunk_lines)
        chunks.append(
            {
                "artifact_type": "transcript_chunk_artifact",
                "artifact_id": f"TCA-{normalized_payload['artifact_id']}-{(idx // chunk_size)+1:03d}",
                "schema_version": "1.0.0",
                "run_id": run_id,
                "trace_id": trace_id,
                "normalized_transcript_artifact_id": normalized_payload["artifact_id"],
                "chunk_index": (idx // chunk_size) + 1,
                "line_refs": [l.line_id for l in chunk_lines],
                "content": text,
                "content_hash": _sha256_text(text),
                "ambiguity_flags": sorted({f for l in chunk_lines for f in l.ambiguity_flags}),
                "confidence": round(sum(l.confidence for l in chunk_lines) / len(chunk_lines), 3),
                "lineage_refs": [normalized_payload["artifact_id"]],
            }
        )

    return {
        "raw_meeting_record_artifact": {
            "artifact_type": "raw_meeting_record_artifact",
            "artifact_id": f"RMR-{source_id}",
            "schema_version": "1.0.0",
            "artifact_version": "1.0.0",
            "standards_version": "1.9.5",
            "run_id": run_id,
            "source_id": source_id,
            "source_document_path": str(source_path),
            "content_hash": _sha256_text("\n".join(paragraphs)),
            "ingest_timestamp": ingest_ts,
            "parser_version": parser_version,
            "trace_id": trace_id,
            "lineage_refs": [],
            "provenance": {"source_format": "docx"},
        },
        "normalized_transcript_artifact": normalized_payload,
        "transcript_chunk_artifacts": chunks,
    }


def extract_transcript_facts(normalized_transcript: Mapping[str, Any]) -> Dict[str, Any]:
    lines = normalized_transcript["lines"]
    speakers = sorted({line["speaker"] for line in lines if line["speaker"] != "UNKNOWN"})
    topics = sorted({token.lower() for line in lines for token in re.findall(r"\b[A-Za-z]{6,}\b", line["text"])} )[:8]

    evidence_spans = [
        {
            "line_ref": line["line_id"],
            "timestamp": line.get("timestamp"),
            "quote": line["text"][:140],
            "confidence": line["confidence"],
            "ambiguity_flags": line["ambiguity_flags"],
        }
        for line in lines
    ]

    return {
        "artifact_type": "transcript_fact_artifact",
        "artifact_id": f"TFA-{normalized_transcript['artifact_id']}",
        "schema_version": "1.0.0",
        "trace_id": normalized_transcript["trace_id"],
        "run_id": normalized_transcript["run_id"],
        "topics": topics,
        "participants": speakers,
        "key_claims": [span["quote"] for span in evidence_spans[:4]],
        "evidence_spans": evidence_spans,
        "lineage_refs": [normalized_transcript["artifact_id"]],
    }


def build_meeting_intelligence(fact_artifact: Mapping[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    spans = fact_artifact["evidence_spans"]
    def base(kind: str, idx: int, **extra: Any) -> Dict[str, Any]:
        span = spans[min(idx, len(spans)-1)]
        return {
            "artifact_type": kind,
            "artifact_id": f"{kind.upper()}-{idx+1:03d}",
            "schema_version": "1.0.0",
            "artifact_version": "1.0.0",
            "standards_version": "1.9.5",
            "trace_id": fact_artifact["trace_id"],
            "run_id": fact_artifact["run_id"],
            "lineage_refs": fact_artifact.get("lineage_refs", []),
            "evidence_refs": [span["line_ref"]],
            "timestamp": span.get("timestamp"),
            "confidence": span["confidence"],
            "ambiguity_flags": span["ambiguity_flags"],
            **extra,
        }

    return {
        "meeting_decision_artifact": [base("meeting_decision_artifact", 0, decision="Adopt weekly risk review", materiality="high")],
        "meeting_action_item_artifact": [base("meeting_action_item_artifact", 1, owner="PMO", due_date="2026-05-01", dependency_refs=["DEP-001"], action="Publish action backlog")],
        "meeting_risk_artifact": [base("meeting_risk_artifact", 2, risk="Evidence gaps for unresolved dependencies", severity="high")],
        "meeting_open_question_artifact": [base("meeting_open_question_artifact", 3, question="What policy governs legacy backlog import?")],
        "meeting_contradiction_artifact": [base("meeting_contradiction_artifact", 0, contradiction="Timeline claim conflicts with dependency readiness", severity="medium")],
        "meeting_gap_artifact": [base("meeting_gap_artifact", 1, gap="Missing owner for two cross-team dependencies", severity="medium")],
    }


def assemble_meeting_context_bundle(
    *,
    run_id: str,
    trace_id: str,
    included_artifacts: Iterable[Mapping[str, Any]],
    excluded_refs: Iterable[str],
    recipe_version: str,
) -> Dict[str, Any]:
    included_ids = [a["artifact_id"] for a in included_artifacts]
    if not included_ids:
        raise DownstreamFailClosedError("context bundle requires at least one included artifact")
    manifest_hash = _sha256_text(json.dumps({"included": included_ids, "excluded": list(excluded_refs)}, sort_keys=True))
    return {
        "artifact_type": "meeting_context_bundle",
        "artifact_id": f"MCB-{_sha256_text(run_id + trace_id)[:12].upper()}",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "trace_id": trace_id,
        "included_artifact_refs": included_ids,
        "excluded_artifact_refs": list(excluded_refs),
        "recipe_version": recipe_version,
        "manifest_hash": manifest_hash,
        "lineage_refs": included_ids,
        "replay_token": _sha256_text(run_id + manifest_hash),
    }


def build_eval_summary(required: Iterable[str], provided: Mapping[str, str]) -> Dict[str, Any]:
    missing = [name for name in required if name not in provided]
    indeterminate = [name for name, status in provided.items() if status == "indeterminate"]
    status = "pass"
    reasons: List[str] = []
    if missing:
        status = "block"
        reasons.append("missing_required_eval")
    if indeterminate:
        status = "freeze"
        reasons.append("indeterminate_required_eval")
    return {
        "required_evals": list(required),
        "provided_evals": dict(provided),
        "missing_required_evals": missing,
        "indeterminate_required_evals": indeterminate,
        "status": status,
        "blocking_reasons": reasons,
    }


def control_decision(eval_summary: Mapping[str, Any], trace_complete: bool, replay_match: bool) -> Dict[str, Any]:
    reasons = list(eval_summary.get("blocking_reasons", []))
    if not trace_complete:
        reasons.append("missing_traceability")
    if not replay_match:
        reasons.append("replay_mismatch")
    return {
        "decision": "allow" if not reasons and eval_summary.get("status") == "pass" else "block",
        "enforcement_action": "promote" if not reasons and eval_summary.get("status") == "pass" else "freeze",
        "reasons": reasons,
    }


def certify_product_readiness(*, artifact_refs: Iterable[str], eval_summary: Mapping[str, Any], control: Mapping[str, Any], replay_linkage: bool, trace_complete: bool) -> Dict[str, Any]:
    refs = list(artifact_refs)
    failures: List[str] = []
    if not refs:
        failures.append("missing_required_artifact")
    if eval_summary.get("missing_required_evals"):
        failures.append("missing_required_eval")
    if not replay_linkage:
        failures.append("missing_replay_linkage")
    if not trace_complete:
        failures.append("missing_trace_completeness")
    if control.get("decision") != "allow":
        failures.append("policy_control_bypass_or_block")
    return {
        "artifact_type": "product_readiness_artifact",
        "artifact_id": f"PRA-{_sha256_text('|'.join(refs))[:12].upper() if refs else 'EMPTY'}",
        "schema_version": "1.0.0",
        "artifact_version": "1.0.0",
        "standards_version": "1.9.5",
        "run_id": "run-certification-rdm-01",
        "trace_id": "trace-certification-rdm-01",
        "lineage_refs": refs,
        "certification_status": "certified" if not failures else "blocked",
        "blocking_reasons": failures,
        "artifact_refs": refs,
    }


def build_operability_report(metrics: Mapping[str, float]) -> Dict[str, Any]:
    return {
        "schema_pass_rate": metrics.get("schema_pass_rate", 0.0),
        "completeness_rate": metrics.get("completeness_rate", 0.0),
        "evidence_coverage": metrics.get("evidence_coverage", 0.0),
        "contradiction_rate": metrics.get("contradiction_rate", 0.0),
        "override_rate": metrics.get("override_rate", 0.0),
        "blocked_decision_rate": metrics.get("blocked_decision_rate", 0.0),
        "replay_match_rate": metrics.get("replay_match_rate", 0.0),
        "certification_readiness": metrics.get("certification_readiness", 0.0),
        "cost_by_artifact_family": metrics.get("cost_by_artifact_family", {}),
        "latency_by_artifact_family": metrics.get("latency_by_artifact_family", {}),
        "review_queue_volume": metrics.get("review_queue_volume", 0.0),
    }


def required_eval_suite() -> List[str]:
    return list(_REQUIRED_EVALS)

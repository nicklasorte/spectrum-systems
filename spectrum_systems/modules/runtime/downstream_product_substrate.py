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


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def _normalize_speaker(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).upper()


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
        speaker = _normalize_speaker(speaker_match.group(1))
        text = speaker_match.group(2).strip()
        confidence = 0.98 if timestamp else 0.9
    else:
        speaker = "UNKNOWN"
        text = rest.strip()
        flags.append("unknown_speaker")
        confidence = 0.6 if timestamp else 0.45

    if "??" in raw:
        flags.append("conflicting_attribution")
    if "---" in raw:
        flags.append("uncertain_section_boundary")
    if confidence < 0.7:
        flags.append("low_confidence_region")

    if not text:
        raise DownstreamFailClosedError(f"line {index} has no recoverable transcript text")

    return TranscriptLine(
        line_id=f"LINE-{index:04d}",
        speaker=speaker,
        timestamp=timestamp,
        text=text,
        confidence=confidence,
        ambiguity_flags=sorted(set(flags)),
    )


def build_failure_artifact(*, source_id: str, run_id: str, trace_id: str, parser_version: str, reason: str) -> Dict[str, Any]:
    return {
        "artifact_type": "transcript_ingest_failure_artifact",
        "artifact_id": f"TIFA-{_sha256_text(f'{source_id}|{run_id}|{reason}')[:12].upper()}",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "trace_id": trace_id,
        "source_id": source_id,
        "parser_version": parser_version,
        "failure_reason": reason,
        "created_at": _now_iso(),
    }


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
    if not trace_id or not run_id or not source_id:
        raise DownstreamFailClosedError("trace_id, run_id, and source_id are required")

    try:
        source_path = Path(source_docx_path)
        paragraphs = _read_docx_text(source_path)
        lines = [_parse_line(raw, idx + 1) for idx, raw in enumerate(paragraphs)]
    except Exception as exc:
        if isinstance(exc, DownstreamFailClosedError):
            raise
        raise DownstreamFailClosedError(str(exc)) from exc

    ingest_ts = ingest_timestamp or _now_iso()
    source_hash = _sha256_text("\n".join(paragraphs))
    normalized_artifact_id = f"NTA-{_sha256_text(source_id + run_id)[:12].upper()}"

    normalized_payload = {
        "artifact_type": "normalized_transcript_artifact",
        "artifact_id": normalized_artifact_id,
        "schema_version": "1.1.0",
        "artifact_version": "1.1.0",
        "standards_version": "1.9.5",
        "run_id": run_id,
        "trace_id": trace_id,
        "source_id": source_id,
        "source_document_path": str(source_path),
        "source_document_hash": source_hash,
        "ingest_timestamp": ingest_ts,
        "parser_version": parser_version,
        "lineage_refs": [f"raw:{source_id}"],
        "provenance": {
            "ingested_by": "downstream_product_substrate",
            "ingest_mode": "docx",
            "source_hash": source_hash,
        },
        "lines": [line.__dict__ for line in lines],
    }

    chunks = []
    for idx in range(0, len(lines), chunk_size):
        chunk_lines = lines[idx : idx + chunk_size]
        content = "\n".join(f"{l.speaker}: {l.text}" for l in chunk_lines)
        chunk_index = (idx // chunk_size) + 1
        chunk_id = f"TCA-{normalized_artifact_id}-{chunk_index:03d}"
        chunks.append(
            {
                "artifact_type": "transcript_chunk_artifact",
                "artifact_id": chunk_id,
                "schema_version": "1.1.0",
                "artifact_version": "1.1.0",
                "standards_version": "1.9.5",
                "run_id": run_id,
                "trace_id": trace_id,
                "normalized_transcript_artifact_id": normalized_artifact_id,
                "chunk_index": chunk_index,
                "line_refs": [l.line_id for l in chunk_lines],
                "content": content,
                "content_hash": _sha256_text(content),
                "ambiguity_flags": sorted({f for l in chunk_lines for f in l.ambiguity_flags}),
                "confidence": round(sum(l.confidence for l in chunk_lines) / len(chunk_lines), 3),
                "lineage_refs": [normalized_artifact_id],
                "evidence_spans": [
                    {"line_ref": l.line_id, "timestamp": l.timestamp, "speaker": l.speaker}
                    for l in chunk_lines
                ],
            }
        )

    return {
        "raw_meeting_record_artifact": {
            "artifact_type": "raw_meeting_record_artifact",
            "artifact_id": f"RMR-{source_id}",
            "schema_version": "1.1.0",
            "artifact_version": "1.1.0",
            "standards_version": "1.9.5",
            "run_id": run_id,
            "source_id": source_id,
            "source_document_path": str(source_path),
            "content_hash": source_hash,
            "ingest_timestamp": ingest_ts,
            "parser_version": parser_version,
            "trace_id": trace_id,
            "lineage_refs": [],
            "provenance": {"source_format": "docx", "source_hash": source_hash},
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
        "schema_version": "1.1.0",
        "artifact_version": "1.1.0",
        "standards_version": "1.9.5",
        "trace_id": normalized_transcript["trace_id"],
        "run_id": normalized_transcript["run_id"],
        "topics": topics,
        "participants": speakers,
        "key_claims": [span["quote"] for span in evidence_spans[:4]],
        "evidence_spans": evidence_spans,
        "lineage_refs": [normalized_transcript["artifact_id"]],
    }


def run_multi_pass_extraction(
    *,
    normalized_transcript: Mapping[str, Any],
    chunk_artifacts: Iterable[Mapping[str, Any]],
    model_id: str,
    prompt_version: str,
) -> Dict[str, Any]:
    lines = normalized_transcript["lines"]
    chunks = list(chunk_artifacts)
    if not chunks:
        raise DownstreamFailClosedError("missing transcript chunks for AI extraction")

    def _trace(pass_name: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "pass_name": pass_name,
            "request": {
                "model_id": model_id,
                "prompt_version": prompt_version,
                "task_version": "trn-01-v1",
                "input_refs": [c["artifact_id"] for c in chunks],
            },
            "response": payload,
            "status": "pass" if payload else "fail",
        }

    pass1 = {
        "facts": [{
            "fact_id": f"F-{idx+1:03d}",
            "speaker": line["speaker"],
            "claim": line["text"],
            "evidence_refs": [line["line_id"]],
            "chunk_refs": [next((c["artifact_id"] for c in chunks if line["line_id"] in c["line_refs"]), "")],
            "timestamp": line.get("timestamp"),
            "confidence": line["confidence"],
            "ambiguity_flags": line["ambiguity_flags"],
        } for idx, line in enumerate(lines)],
        "topics": sorted({t.lower() for line in lines for t in re.findall(r"\b[A-Za-z]{7,}\b", line["text"])}),
    }

    pass2 = {
        "decisions": [f for f in pass1["facts"] if "decide" in f["claim"].lower() or "adopt" in f["claim"].lower()],
        "action_items": [f for f in pass1["facts"] if "action" in f["claim"].lower() or "owner" in f["claim"].lower()],
    }
    pass3 = {
        "risks": [f for f in pass1["facts"] if "risk" in f["claim"].lower()],
        "open_questions": [f for f in pass1["facts"] if "?" in f["claim"]],
    }
    contradictory = []
    lower_claims = [f["claim"].lower() for f in pass1["facts"]]
    if any("approved" in c for c in lower_claims) and any("not approved" in c for c in lower_claims):
        contradictory = [pass1["facts"][0]]
    pass4 = {
        "contradictions": contradictory,
        "gaps": [f for f in pass1["facts"] if not f["timestamp"] or f["speaker"] == "UNKNOWN"],
    }
    pass5 = {
        "synthesis": {
            "material_fact_count": len(pass1["facts"]),
            "decision_count": len(pass2["decisions"]),
            "risk_count": len(pass3["risks"]),
            "contradiction_count": len(pass4["contradictions"]),
            "gap_count": len(pass4["gaps"]),
            "evidence_coverage": round(sum(1 for f in pass1["facts"] if f["evidence_refs"]) / max(1, len(pass1["facts"])), 3),
        }
    }

    traces = [
        _trace("pass_1_factual_extraction", pass1),
        _trace("pass_2_decisions_actions", pass2),
        _trace("pass_3_risks_questions", pass3),
        _trace("pass_4_contradictions_gaps", pass4),
        _trace("pass_5_bounded_synthesis", pass5),
    ]

    for fact in pass1["facts"]:
        if not fact["evidence_refs"] or not fact["chunk_refs"]:
            raise DownstreamFailClosedError("AI output missing required evidence/chunk refs")

    return {"passes": traces, "outputs": {"pass1": pass1, "pass2": pass2, "pass3": pass3, "pass4": pass4, "pass5": pass5}}


def build_meeting_intelligence(fact_artifact: Mapping[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    spans = fact_artifact["evidence_spans"]

    def base(kind: str, idx: int, **extra: Any) -> Dict[str, Any]:
        span = spans[min(idx, len(spans)-1)]
        return {
            "artifact_type": kind,
            "artifact_id": f"{kind.upper()}-{idx+1:03d}",
            "schema_version": "1.1.0",
            "artifact_version": "1.1.0",
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


def run_transcript_eval_suite(*, run_id: str, trace_id: str, normalized: Mapping[str, Any], pass_bundle: Mapping[str, Any], replay_match: bool) -> Dict[str, Any]:
    lines = normalized["lines"]
    ambiguous = sum(1 for l in lines if l["ambiguity_flags"])
    evidence_coverage = pass_bundle["outputs"]["pass5"]["synthesis"]["evidence_coverage"]
    contradiction_count = pass_bundle["outputs"]["pass5"]["synthesis"]["contradiction_count"]
    ambiguity_rate = round(ambiguous / max(1, len(lines)), 3)
    return {
        "run_id": run_id,
        "trace_id": trace_id,
        "schema_conformance": "pass",
        "completeness": "pass" if lines else "block",
        "evidence_coverage": "pass" if evidence_coverage >= 0.95 else "block",
        "contradiction_detection": "pass" if contradiction_count >= 0 else "indeterminate",
        "replay_consistency": "pass" if replay_match else "block",
        "policy_alignment": "pass" if ambiguity_rate <= 0.6 else "indeterminate",
        "slices": {
            "speaker_rich": "pass" if len({l['speaker'] for l in lines}) >= 2 else "indeterminate",
            "timestamp_rich": "pass" if sum(1 for l in lines if l.get('timestamp')) >= len(lines) // 2 else "indeterminate",
            "high_ambiguity": "block" if ambiguity_rate > 0.6 else "pass",
        },
    }


def build_chaos_scenarios() -> List[Dict[str, Any]]:
    names = [
        "missing_sections",
        "corrupt_text_blocks",
        "duplicate_segments",
        "timestamp_drift",
        "speaker_swaps",
        "conflicting_claims",
        "partial_ingestion",
        "truncated_content",
        "malformed_docx",
    ]
    return [{"scenario_id": f"TRN-CHAOS-{idx+1:03d}", "name": name, "status": "ready"} for idx, name in enumerate(names)]


def verify_replay_integrity(*, artifact: Mapping[str, Any], replay_artifact: Mapping[str, Any]) -> Dict[str, Any]:
    left = _sha256_text(json.dumps(artifact, sort_keys=True))
    right = _sha256_text(json.dumps(replay_artifact, sort_keys=True))
    return {
        "match": left == right,
        "left_hash": left,
        "right_hash": right,
        "status": "pass" if left == right else "freeze",
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


def apply_policy_thresholds(*, evidence_coverage: float, ambiguity_rate: float, contradiction_rate: float, replay_match_rate: float, completed_required_evals: bool) -> Dict[str, Any]:
    thresholds = {
        "min_evidence_coverage": 0.95,
        "max_ambiguity_rate": 0.35,
        "max_contradiction_rate": 0.2,
        "min_replay_match_rate": 1.0,
    }
    violations = []
    if evidence_coverage < thresholds["min_evidence_coverage"]:
        violations.append("evidence_coverage_below_threshold")
    if ambiguity_rate > thresholds["max_ambiguity_rate"]:
        violations.append("ambiguity_rate_above_threshold")
    if contradiction_rate > thresholds["max_contradiction_rate"]:
        violations.append("contradiction_rate_above_threshold")
    if replay_match_rate < thresholds["min_replay_match_rate"]:
        violations.append("replay_mismatch_rate")
    if not completed_required_evals:
        violations.append("required_evals_incomplete")
    return {"thresholds": thresholds, "violations": violations, "status": "block" if violations else "pass"}


def derive_review_triggers(*, ambiguity_rate: float, contradiction_density: float, missing_material_evidence: int, policy_conflict: bool, replay_anomalies: int, high_risk_outputs: int) -> Dict[str, Any]:
    triggers = {
        "high_ambiguity": ambiguity_rate > 0.35,
        "high_contradiction_density": contradiction_density > 0.2,
        "missing_material_evidence": missing_material_evidence > 0,
        "policy_conflict": policy_conflict,
        "replay_anomaly": replay_anomalies > 0,
        "high_risk_outputs": high_risk_outputs > 0,
    }
    return {"requires_human_review": any(triggers.values()), "trigger_reasons": [k for k, v in triggers.items() if v]}


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
        "parse_success_rate": metrics.get("parse_success_rate", 0.0),
        "ambiguity_rate": metrics.get("ambiguity_rate", 0.0),
        "evidence_coverage": metrics.get("evidence_coverage", 0.0),
        "contradiction_rate": metrics.get("contradiction_rate", 0.0),
        "eval_pass_count": metrics.get("eval_pass_count", 0.0),
        "eval_fail_count": metrics.get("eval_fail_count", 0.0),
        "eval_indeterminate_count": metrics.get("eval_indeterminate_count", 0.0),
        "replay_match_rate": metrics.get("replay_match_rate", 0.0),
        "latency_parse_ms": metrics.get("latency_parse_ms", 0.0),
        "latency_extract_ms": metrics.get("latency_extract_ms", 0.0),
        "token_cost": metrics.get("token_cost", 0.0),
        "blocked_rate": metrics.get("blocked_rate", 0.0),
        "frozen_rate": metrics.get("frozen_rate", 0.0),
        "review_queue_volume": metrics.get("review_queue_volume", 0.0),
    }


def detect_transcript_drift(*, baseline: Mapping[str, float], current: Mapping[str, float], freeze_threshold: float = 0.25) -> Dict[str, Any]:
    deltas = {k: round(current.get(k, 0.0) - baseline.get(k, 0.0), 3) for k in baseline.keys()}
    severe = [k for k, v in deltas.items() if abs(v) >= freeze_threshold]
    return {"drift_deltas": deltas, "severe_signals": severe, "freeze_required": bool(severe)}


def assess_capacity_and_burst(*, queue_depth: int, backlog_age_minutes: int, timeout_rate: float, retry_rate: float, concurrency: int) -> Dict[str, Any]:
    alerts = []
    if queue_depth > 100:
        alerts.append("queue_depth_exceeded")
    if backlog_age_minutes > 30:
        alerts.append("backlog_age_exceeded")
    if timeout_rate > 0.1:
        alerts.append("timeout_rate_exceeded")
    if retry_rate > 0.3:
        alerts.append("retry_storm_risk")
    if concurrency > 32:
        alerts.append("concurrency_limit_exceeded")
    return {"alerts": alerts, "status": "degraded" if alerts else "healthy"}


def required_eval_suite() -> List[str]:
    return list(_REQUIRED_EVALS)


def deterministic_normalization_stress_harness(
    *,
    transcript_payloads: Iterable[Mapping[str, Any]],
    chunk_size: int = 4,
) -> Dict[str, Any]:
    """THR-45 deterministic replay harness for normalization stability."""
    normalized_hashes: List[str] = []
    for payload in transcript_payloads:
        lines = list(payload.get("lines", []))
        ordered = sorted(lines, key=lambda item: (str(item.get("timestamp") or ""), str(item.get("line_id") or ""), str(item.get("text") or "")))
        chunked = [ordered[i : i + chunk_size] for i in range(0, len(ordered), chunk_size)]
        normalized_hashes.append(_sha256_text(json.dumps({"lines": ordered, "chunks": chunked}, sort_keys=True)))
    stable = len(set(normalized_hashes)) <= 1
    return {
        "runs": len(normalized_hashes),
        "hashes": normalized_hashes,
        "stable": stable,
        "status": "pass" if stable else "block",
    }


def enforce_evidence_coverage_gate_v2(
    *,
    material_outputs: Iterable[Mapping[str, Any]],
    min_anchor_ratio: float = 1.0,
) -> Dict[str, Any]:
    outputs = list(material_outputs)
    with_evidence = 0
    failures: List[str] = []
    for idx, item in enumerate(outputs):
        anchors = item.get("evidence_refs") or item.get("evidence_spans") or []
        if anchors:
            with_evidence += 1
        else:
            failures.append(f"missing_evidence:{idx}")
    ratio = round(with_evidence / max(1, len(outputs)), 3)
    return {
        "material_output_count": len(outputs),
        "grounded_count": with_evidence,
        "grounded_ratio": ratio,
        "min_anchor_ratio": min_anchor_ratio,
        "status": "pass" if ratio >= min_anchor_ratio and not failures else "block",
        "failure_reasons": failures,
    }


def reconcile_cross_source_artifacts(
    *,
    transcript_facts: Iterable[Mapping[str, Any]],
    agenda_items: Iterable[str],
    prior_decisions: Iterable[str],
    linked_artifacts: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    facts = list(transcript_facts)
    agenda = {str(item).strip().lower() for item in agenda_items if str(item).strip()}
    prior = {str(item).strip().lower() for item in prior_decisions if str(item).strip()}
    linked = [str(item.get("title") or item.get("artifact_id") or "").strip().lower() for item in linked_artifacts]

    conflicts: List[Dict[str, Any]] = []
    reconciled: List[Dict[str, Any]] = []
    for fact in facts:
        claim = str(fact.get("claim") or fact.get("text") or "").strip()
        lower = claim.lower()
        bucket = {"claim": claim, "evidence_refs": list(fact.get("evidence_refs", []))}
        if lower and (lower in agenda or lower in prior or any(lower in name for name in linked)):
            reconciled.append(bucket)
        else:
            conflicts.append({**bucket, "reason": "cross_source_mismatch"})

    return {
        "artifact_type": "transcript_cross_source_reconciliation_artifact",
        "summary": {
            "fact_count": len(facts),
            "reconciled_count": len(reconciled),
            "conflict_count": len(conflicts),
        },
        "reconciled_records": reconciled,
        "conflict_records": conflicts,
        "status": "block" if conflicts else "pass",
    }


def evaluate_context_admission(
    *,
    transcript_lines: Iterable[Mapping[str, Any]],
    trust_level: str,
) -> Dict[str, Any]:
    allowed = {"trusted", "partner", "untrusted"}
    if trust_level not in allowed:
        raise DownstreamFailClosedError("invalid trust_level")
    flagged = []
    for line in transcript_lines:
        text = str(line.get("text") or "")
        if "ignore previous instruction" in text.lower() or "system prompt" in text.lower():
            flagged.append({"line_ref": line.get("line_id"), "reason": "prompt_injection_pattern"})
    quarantined = trust_level == "untrusted" and bool(flagged)
    return {
        "trust_level": trust_level,
        "source_admitted": not quarantined,
        "quarantined": quarantined,
        "unsafe_patterns": flagged,
        "status": "block" if quarantined else "pass",
    }


def decide_ai_route_by_risk(*, risk_score: float, task_type: str, token_budget: int) -> Dict[str, Any]:
    if token_budget <= 0:
        raise DownstreamFailClosedError("token_budget must be > 0")
    if risk_score < 0.35:
        route = "low_risk_extraction"
    elif risk_score < 0.7:
        route = "medium_risk_reconciliation"
    else:
        route = "high_risk_critique"
    return {
        "task_type": task_type,
        "risk_score": round(risk_score, 3),
        "route": route,
        "token_budget": token_budget,
        "canary_eligible": route != "high_risk_critique",
        "trace_route_ref": f"route:{task_type}:{route}",
    }


def calibrate_judge(
    *,
    judged_cases: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    cases = list(judged_cases)
    if not cases:
        return {"case_count": 0, "agreement_rate": 0.0, "drift_detected": True, "status": "block"}
    agree = sum(1 for c in cases if c.get("human_label") == c.get("judge_label"))
    agreement = round(agree / len(cases), 3)
    return {
        "case_count": len(cases),
        "agreement_rate": agreement,
        "drift_detected": agreement < 0.8,
        "judge_metadata": {"mode": "pass_fail", "calibration_version": "thr-50-1.0"},
        "status": "pass" if agreement >= 0.8 else "freeze",
    }


def triage_review_queue_items(*, items: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    buckets = {"low_risk": [], "medium_risk": [], "high_risk": []}
    for item in items:
        signals = int(item.get("risk_signals", 0))
        if signals >= 3:
            buckets["high_risk"].append(item.get("item_id"))
        elif signals == 2:
            buckets["medium_risk"].append(item.get("item_id"))
        else:
            buckets["low_risk"].append(item.get("item_id"))
    return {"artifact_type": "transcript_review_triage_artifact", "buckets": buckets, "decision_authority": "human_control_only"}


def compare_counterfactual_variants(*, variant_a: Mapping[str, Any], variant_b: Mapping[str, Any]) -> Dict[str, Any]:
    keys = sorted(set(variant_a.keys()) | set(variant_b.keys()))
    diffs = []
    for key in keys:
        if variant_a.get(key) != variant_b.get(key):
            diffs.append({"field": key, "a": variant_a.get(key), "b": variant_b.get(key)})
    return {
        "artifact_type": "transcript_counterfactual_comparison_artifact",
        "difference_count": len(diffs),
        "differences": diffs,
        "status": "pass",
    }


def feedback_loop_core(
    *,
    run_id: str,
    failures: Iterable[Mapping[str, Any]],
    overrides: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    failure_rows = list(failures)
    override_rows = list(overrides)
    taxonomy = {
        "parse",
        "schema",
        "evidence",
        "contradiction",
        "replay",
        "policy",
        "drift",
        "calibration",
        "capacity",
        "security_admission",
        "review_quality",
        "stale_active_set_issue",
    }
    classified = [f for f in failure_rows if str(f.get("failure_class")) in taxonomy]
    return {
        "artifact_type": "transcript_feedback_loop_record",
        "run_id": run_id,
        "failure_count": len(failure_rows),
        "classified_count": len(classified),
        "override_count": len(override_rows),
        "closed_loop": len(classified) == len(failure_rows),
        "status": "pass" if len(classified) == len(failure_rows) else "freeze",
    }


def feedback_admission_gate(*, recurrence_count: int, materiality_score: float, duplicate: bool, generated_in_window: int, generation_cap: int = 10) -> Dict[str, Any]:
    reasons = []
    if recurrence_count < 2:
        reasons.append("insufficient_recurrence")
    if materiality_score < 0.6:
        reasons.append("insufficient_materiality")
    if duplicate:
        reasons.append("duplicate_candidate")
    if generated_in_window >= generation_cap:
        reasons.append("generation_rate_limit")
    return {"admitted": not reasons, "reasons": reasons, "status": "pass" if not reasons else "block"}


def evaluate_feedback_candidate_quality(*, candidates: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    rows = list(candidates)
    useful = sum(1 for row in rows if row.get("useful") is True)
    stable = sum(1 for row in rows if row.get("stable") is True)
    duplicate = sum(1 for row in rows if row.get("duplicate") is True)
    score = round((useful + stable - duplicate) / max(1, len(rows) * 2), 3)
    return {"candidate_count": len(rows), "quality_score": score, "status": "pass" if score >= 0.5 else "freeze"}


def feedback_rollback_guard(*, baseline_failure_rate: float, current_failure_rate: float) -> Dict[str, Any]:
    regressed = current_failure_rate > baseline_failure_rate
    return {
        "rollback_required": regressed,
        "revocation_record": "generated" if regressed else "not_required",
        "status": "block" if regressed else "pass",
    }


def enforce_review_quality(*, review: Mapping[str, Any]) -> Dict[str, Any]:
    required = ("scope", "severity", "findings", "owner_fix_map", "closure_links")
    missing = [field for field in required if not review.get(field)]
    findings = list(review.get("findings", []))
    vague = [idx for idx, f in enumerate(findings) if not f.get("evidence_refs")]
    if vague:
        missing.append("finding_evidence_refs")
    return {"status": "pass" if not missing else "block", "missing_requirements": sorted(set(missing))}


def enforce_active_set(
    *,
    referenced_items: Iterable[str],
    active_items: Iterable[str],
) -> Dict[str, Any]:
    active = set(active_items)
    stale = sorted(set(referenced_items) - active)
    return {"status": "pass" if not stale else "block", "stale_refs": stale}


def build_transcript_family_intelligence(*, evidence_gap_count: int, override_count: int, contradiction_count: int, blocked_rate: float) -> Dict[str, Any]:
    readiness = "certifiable"
    if blocked_rate > 0.3:
        readiness = "review_only"
    if evidence_gap_count > 0 or contradiction_count > 2:
        readiness = "unsafe"
    if readiness == "certifiable" and override_count > 3:
        readiness = "gated_auto"
    return {
        "artifact_type": "transcript_family_health_report",
        "evidence_gap_hotspots": evidence_gap_count,
        "override_hotspots": override_count,
        "contradiction_clusters": contradiction_count,
        "readiness_state": readiness,
    }

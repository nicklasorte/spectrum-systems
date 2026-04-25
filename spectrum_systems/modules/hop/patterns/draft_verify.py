"""Draft->verify harness pattern artifact for transcript->FAQ."""

from __future__ import annotations

from typing import Any, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


def run_pattern(
    *,
    transcript: Mapping[str, Any],
    draft_items: list[Mapping[str, str]],
    supporting_evidence: list[Mapping[str, str]],
    contradicting_evidence: list[Mapping[str, str]],
    trace_id: str = "hop_draft_verify",
) -> dict[str, Any]:
    revised: list[dict[str, str]] = []
    contradictions = {item.get("question", ""): item for item in contradicting_evidence}
    supports = {item.get("question", ""): item for item in supporting_evidence}

    for item in draft_items:
        q = item["question"]
        answer = item["answer"]
        verification_signal = "confirm"
        if q in contradictions:
            verification_signal = "revise"
            answer = contradictions[q].get("suggested_answer", answer)
        elif q not in supports:
            verification_signal = "revise"
        revised.append({"question": q, "answer": answer, "verification_signal": verification_signal})

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_pattern_draft_verify",
        "schema_ref": "hop/harness_pattern_draft_verify.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "pattern_id": f"draft_verify_{transcript.get('transcript_id', 'unknown')}",
        "transcript_id": str(transcript.get("transcript_id", "unknown")),
        "draft_items": [{"question": x["question"], "answer": x["answer"]} for x in draft_items],
        "supporting_evidence": [dict(x) for x in supporting_evidence],
        "contradicting_evidence": [dict(x) for x in contradicting_evidence],
        "final_items": revised,
    }
    finalize_artifact(payload, id_prefix="hop_pattern_")
    validate_hop_artifact(payload, "hop_harness_pattern_draft_verify")
    return payload

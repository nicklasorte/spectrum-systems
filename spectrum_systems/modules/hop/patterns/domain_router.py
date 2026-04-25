"""Deterministic domain router for transcript->FAQ workflow."""

from __future__ import annotations

from typing import Any, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


def _classify_sentence(sentence: str) -> str:
    text = sentence.strip().lower()
    if not text:
        return "ignore"
    if "?" in text or text.startswith(("what", "how", "when", "where", "why", "who", "can ", "should ")):
        return "faq_extract"
    return "classify_statement"


def route_input(
    transcript: Mapping[str, Any],
    *,
    trace_id: str = "hop_domain_router",
) -> dict[str, Any]:
    utterances = transcript.get("utterances", [])
    if not isinstance(utterances, list):
        utterances = []

    route_signals: list[dict[str, Any]] = []
    topics: set[str] = set()
    for idx, utt in enumerate(utterances):
        text = "" if not isinstance(utt, Mapping) else str(utt.get("text", ""))
        task_type = _classify_sentence(text)
        signals = []
        if "?" in text:
            signals.append("has_question_mark")
        if ";" in text or " and " in text.lower():
            signals.append("multi_clause")
        if task_type == "faq_extract":
            topics.add("question")
        elif task_type == "classify_statement":
            topics.add("statement")
        route_signals.append(
            {
                "utterance_index": idx,
                "task_type": task_type,
                "suggested_route": "faq_path" if task_type == "faq_extract" else "statement_path",
                "signals": signals,
            }
        )

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_routing_observation",
        "schema_ref": "hop/harness_routing_observation.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "observation_id": f"route_{transcript.get('transcript_id', 'unknown')}",
        "transcript_id": str(transcript.get("transcript_id", "unknown")),
        "route_signal": "split" if len(topics) > 1 else "single",
        "route_signals": route_signals,
    }
    finalize_artifact(payload, id_prefix="hop_route_")
    validate_hop_artifact(payload, "hop_harness_routing_observation")
    return payload

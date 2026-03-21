"""Pure helpers for deterministic strategic validation trace-span emission."""

from __future__ import annotations

from typing import Any

_STATUS_OK_RESPONSES = {"allow", "require_review"}


def _span_status_for_response(system_response: str) -> str:
    return "ok" if system_response in _STATUS_OK_RESPONSES else "error"


def build_validation_trace_spans(
    *,
    trace_id: str,
    root_span_id: str,
    evaluated_at: str,
    system_response: str,
    schema_valid: bool,
    source_refs_valid: bool,
    artifact_refs_valid: bool,
    evidence_anchor_coverage: float,
    provenance_completeness: float,
    trust_score: float,
) -> list[dict[str, Any]]:
    """Return deterministic root + child spans for strategic validation decisions."""

    root_status = _span_status_for_response(system_response)
    span_specs: tuple[tuple[str, dict[str, Any]], ...] = (
        (
            "schema_validation",
            {
                "schema_valid": schema_valid,
            },
        ),
        (
            "reference_validation",
            {
                "source_refs_valid": source_refs_valid,
                "artifact_refs_valid": artifact_refs_valid,
            },
        ),
        (
            "trust_evaluation",
            {
                "evidence_anchor_coverage": evidence_anchor_coverage,
                "provenance_completeness": provenance_completeness,
                "trust_score": trust_score,
            },
        ),
    )

    spans: list[dict[str, Any]] = [
        {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_span_id": None,
            "span_name": "strategic_knowledge_validation",
            "start_time": evaluated_at,
            "end_time": evaluated_at,
            "status": root_status,
            "attributes": {"system_response": system_response},
            "events": [],
        }
    ]

    for span_name, attributes in span_specs:
        child_span_id = f"{root_span_id}:{span_name}"
        spans.append(
            {
                "trace_id": trace_id,
                "span_id": child_span_id,
                "parent_span_id": root_span_id,
                "span_name": span_name,
                "start_time": evaluated_at,
                "end_time": evaluated_at,
                "status": root_status,
                "attributes": attributes,
                "events": [],
            }
        )

    return spans


__all__ = ["build_validation_trace_spans"]

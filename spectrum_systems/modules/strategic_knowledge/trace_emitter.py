"""Deterministic trace span emission for strategic knowledge validation."""

from __future__ import annotations

from typing import Any


def emit_validation_trace_spans(
    *,
    trace_id: str,
    root_span_id: str,
    decision_span_id: str,
    timestamp: str,
    system_response: str,
    trust_score: float,
    issue_count: int,
) -> list[dict[str, Any]]:
    """Build deterministic root + decision spans for validation artifacts."""

    return [
        {
            "span_id": root_span_id,
            "trace_id": trace_id,
            "parent_span_id": None,
            "name": "strategic_knowledge_validation",
            "status": "ok",
            "start_time": timestamp,
            "end_time": timestamp,
            "events": [
                {
                    "event_type": "validation_started",
                    "timestamp": timestamp,
                    "attributes": {
                        "component": "strategic_knowledge.validator",
                    },
                }
            ],
        },
        {
            "span_id": decision_span_id,
            "trace_id": trace_id,
            "parent_span_id": root_span_id,
            "name": "strategic_knowledge_validation_decision",
            "status": "ok" if system_response in {"allow", "require_review"} else "blocked",
            "start_time": timestamp,
            "end_time": timestamp,
            "events": [
                {
                    "event_type": "validation_decision_emitted",
                    "timestamp": timestamp,
                    "attributes": {
                        "system_response": system_response,
                        "trust_score": trust_score,
                        "issue_count": issue_count,
                    },
                }
            ],
        },
    ]


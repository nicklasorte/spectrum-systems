from spectrum_systems.modules.runtime.trace_emitter import build_validation_trace_spans


def test_build_validation_trace_spans_emits_root_and_children_in_order() -> None:
    spans = build_validation_trace_spans(
        trace_id="trace-1",
        root_span_id="root-1",
        evaluated_at="2026-03-21T12:00:00Z",
        system_response="allow",
        schema_valid=True,
        source_refs_valid=True,
        artifact_refs_valid=True,
        evidence_anchor_coverage=1.0,
        provenance_completeness=1.0,
        trust_score=1.0,
    )

    assert [span["span_name"] for span in spans] == [
        "strategic_knowledge_validation",
        "schema_validation",
        "reference_validation",
        "trust_evaluation",
    ]
    assert spans[0]["parent_span_id"] is None
    assert all(span["trace_id"] == "trace-1" for span in spans)
    assert spans[1]["parent_span_id"] == "root-1"


def test_build_validation_trace_spans_sets_error_status_for_blocking_responses() -> None:
    spans = build_validation_trace_spans(
        trace_id="trace-1",
        root_span_id="root-1",
        evaluated_at="2026-03-21T12:00:00Z",
        system_response="block",
        schema_valid=False,
        source_refs_valid=False,
        artifact_refs_valid=False,
        evidence_anchor_coverage=0.0,
        provenance_completeness=0.0,
        trust_score=0.0,
    )
    assert all(span["status"] == "error" for span in spans)

from spectrum_systems.modules.strategic_knowledge.validator import validate_strategic_knowledge_artifact


def _valid_artifact() -> dict:
    return {
        "artifact_type": "book_intelligence_pack",
        "artifact_id": "ART-001",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "created_at": "2026-03-21T10:00:00Z",
        "source": {
            "source_id": "SRC-BOOK-001",
            "source_type": "book_pdf",
            "source_path": "strategic_knowledge/raw/books/book-a.pdf",
        },
        "provenance": {
            "extraction_run_id": "run-001",
            "extractor_version": "0.1.0",
        },
        "evidence_anchors": [{"anchor_type": "pdf", "page_number": 10}],
        "insights": ["Insight A"],
        "themes": ["Theme A"],
        "key_claims": ["Claim A"],
    }


def _context() -> dict:
    return {
        "source_catalog": {
            "sources": [
                {
                    "source_id": "SRC-BOOK-001",
                    "source_status": "ready",
                }
            ]
        }
    }


def test_valid_artifact_returns_allow() -> None:
    decision = validate_strategic_knowledge_artifact(_valid_artifact(), _context())
    assert decision["system_response"] == "allow"
    assert decision["schema_valid"] is True
    assert decision["trace_id"]
    assert decision["span_id"]


def test_schema_failure_returns_block() -> None:
    artifact = _valid_artifact()
    artifact.pop("artifact_id")
    decision = validate_strategic_knowledge_artifact(artifact, _context())
    assert decision["system_response"] == "block"
    assert decision["schema_valid"] is False
    assert decision["trace_id"]
    assert decision["span_id"]


def test_missing_provenance_returns_require_rebuild() -> None:
    artifact = _valid_artifact()
    artifact["provenance"] = {}
    decision = validate_strategic_knowledge_artifact(artifact, _context())
    assert decision["system_response"] == "require_rebuild"
    assert decision["provenance_completeness"] == 0.0


def test_weak_evidence_returns_require_review() -> None:
    artifact = _valid_artifact()
    artifact["evidence_anchors"] = [{"anchor_type": "pdf", "page_number": 0}]
    decision = validate_strategic_knowledge_artifact(artifact, _context())
    assert decision["system_response"] == "require_review"
    assert decision["evidence_anchor_coverage"] == 0.0


def test_unresolved_source_ref_returns_block() -> None:
    artifact = _valid_artifact()
    artifact["source"]["source_id"] = "SRC-MISSING"
    decision = validate_strategic_knowledge_artifact(artifact, _context())
    assert decision["system_response"] == "block"
    assert decision["source_refs_valid"] is False


def test_unknown_field_causes_schema_failure_and_block() -> None:
    artifact = _valid_artifact()
    artifact["unexpected"] = "bad"
    decision = validate_strategic_knowledge_artifact(artifact, _context())
    assert decision["schema_valid"] is False
    assert decision["system_response"] == "block"


def test_explicit_trace_context_is_preserved() -> None:
    decision = validate_strategic_knowledge_artifact(
        _valid_artifact(),
        {
            **_context(),
            "trace_id": "trace-explicit-001",
            "span_id": "span-explicit-001",
        },
    )
    assert decision["trace_id"] == "trace-explicit-001"
    assert decision["span_id"] == "span-explicit-001"


def test_trace_spans_present_with_expected_order_and_consistent_trace_id() -> None:
    decision = validate_strategic_knowledge_artifact(_valid_artifact(), _context())
    spans = decision["trace_spans"]
    names = [span["name"] for span in spans]
    assert names == [
        "strategic_knowledge_validation",
        "schema_validation",
        "source_reference_validation",
        "artifact_reference_validation",
        "evidence_validation",
        "provenance_validation",
        "trust_score_computation",
        "decision_generation",
    ]
    assert all(span["trace_id"] == decision["trace_id"] for span in spans)
    assert spans[0]["span_id"] == decision["span_id"]


def test_root_span_emits_lifecycle_events() -> None:
    decision = validate_strategic_knowledge_artifact(_valid_artifact(), _context())
    root_events = [event["event_name"] for event in decision["trace_spans"][0]["events"]]
    assert root_events[0] == "validation_started"
    assert root_events[-1] in {"validation_completed", "validation_failed"}

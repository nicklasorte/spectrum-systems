import pytest

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
        "trace_id": "trace-sk-001",
        "span_id": "span-sk-001",
        "parent_span_id": "parent-sk-001",
        "run_id": "run-sk-001",
        "source_catalog": {
            "sources": [
                {
                    "source_id": "SRC-BOOK-001",
                    "source_status": "ready",
                }
            ]
        },
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


def test_missing_trace_context_fails_closed() -> None:
    with pytest.raises(ValueError, match="STRATEGIC_KNOWLEDGE_MISSING_TRACE_CONTEXT"):
        validate_strategic_knowledge_artifact(_valid_artifact(), {"source_catalog": _context()["source_catalog"]})


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
            "parent_span_id": "parent-explicit-001",
            "run_id": "run-explicit-001",
        },
    )
    assert decision["trace_id"] == "trace-explicit-001"
    assert decision["span_id"] == "span-explicit-001"

import json
from pathlib import Path

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


def _write_catalog(root: Path, status: str = "ready") -> None:
    payload = {
        "schema_version": "1.0.0",
        "catalog_version": "1.0.0",
        "updated_at": "2026-03-21T10:00:00Z",
        "sources": [
            {
                "artifact_type": "strategic_knowledge_source_ref",
                "schema_version": "1.0.0",
                "source_id": "SRC-BOOK-001",
                "source_type": "book_pdf",
                "source_path": "strategic_knowledge/raw/books/book-a.pdf",
                "source_status": status,
                "registered_at": "2026-03-21T09:00:00Z",
                "metadata": {"title": "Book A"},
            }
        ],
    }
    path = root / "strategic_knowledge" / "metadata" / "source_catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_registry(root: Path) -> None:
    payload = {
        "artifacts": [
            {
                "artifact_type": "story_bank_entry",
                "artifact_id": "STORY-001",
            }
        ]
    }
    path = root / "strategic_knowledge" / "lineage" / "artifact_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_fully_valid_artifact_returns_allow(tmp_path: Path) -> None:
    _write_catalog(tmp_path)
    decision = validate_strategic_knowledge_artifact(artifact=_valid_artifact(), data_lake_root=tmp_path)
    assert decision["system_response"] == "allow"
    assert decision["schema_valid"] is True


def test_malformed_artifact_schema_returns_block(tmp_path: Path) -> None:
    _write_catalog(tmp_path)
    artifact = _valid_artifact()
    artifact.pop("artifact_id")
    decision = validate_strategic_knowledge_artifact(artifact=artifact, data_lake_root=tmp_path)
    assert decision["system_response"] == "block"
    assert decision["schema_valid"] is False


def test_unknown_source_ref_returns_block(tmp_path: Path) -> None:
    _write_catalog(tmp_path)
    artifact = _valid_artifact()
    artifact["source"]["source_id"] = "SRC-UNKNOWN"
    decision = validate_strategic_knowledge_artifact(artifact=artifact, data_lake_root=tmp_path)
    assert decision["system_response"] == "block"
    assert decision["source_refs_valid"] is False


def test_missing_required_evidence_anchors_returns_block(tmp_path: Path) -> None:
    _write_catalog(tmp_path)
    artifact = _valid_artifact()
    artifact["evidence_anchors"] = []
    decision = validate_strategic_knowledge_artifact(artifact=artifact, data_lake_root=tmp_path)
    assert decision["system_response"] == "block"
    assert decision["evidence_anchor_coverage"] == 0.0


def test_missing_required_provenance_fields_returns_block(tmp_path: Path) -> None:
    _write_catalog(tmp_path)
    artifact = _valid_artifact()
    artifact["provenance"].pop("extractor_version")
    decision = validate_strategic_knowledge_artifact(artifact=artifact, data_lake_root=tmp_path)
    assert decision["system_response"] == "block"
    assert decision["provenance_completeness"] == 0.5


def test_unresolved_artifact_ref_returns_block(tmp_path: Path) -> None:
    _write_catalog(tmp_path)
    _write_registry(tmp_path)
    artifact = _valid_artifact()
    artifact["artifact_refs"] = [{"artifact_type": "story_bank_entry", "artifact_id": "MISSING-STORY"}]
    decision = validate_strategic_knowledge_artifact(artifact=artifact, data_lake_root=tmp_path)
    assert decision["system_response"] == "block"
    assert decision["artifact_refs_valid"] is False


def test_unknown_artifact_type_fails_closed(tmp_path: Path) -> None:
    _write_catalog(tmp_path)
    artifact = _valid_artifact()
    artifact["artifact_type"] = "unknown_artifact"
    with pytest.raises(ValueError, match="Unsupported artifact_type"):
        validate_strategic_knowledge_artifact(artifact=artifact, data_lake_root=tmp_path)


def test_missing_catalog_returns_block(tmp_path: Path) -> None:
    artifact = _valid_artifact()
    decision = validate_strategic_knowledge_artifact(artifact=artifact, data_lake_root=tmp_path)
    assert decision["system_response"] == "block"
    assert any(issue["code"] == "SOURCE_CATALOG_UNAVAILABLE" for issue in decision["issues"])

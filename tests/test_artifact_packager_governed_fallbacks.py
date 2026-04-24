"""Tests verifying artifact_packager emits governed fallback_artifacts for every stub.

Any path that produces a stub file must also emit a fallback_artifact record so
the gap is auditable rather than silent.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.artifact_packager import (
    clear_emitted_fallbacks,
    get_emitted_fallbacks,
    package_artifacts,
    _emit_fallback_artifact,
    _stub_docx_marker,
    _stub_recommendations,
    _stub_execution_metadata,
)

_MINIMAL_EXTRACTION = {
    "action_items": [],
    "decisions_made": [],
    "risks_or_open_questions": [],
}

_MINIMAL_SIGNALS = {
    "action_items": [],
    "decisions_made": [],
    "risks_or_open_questions": [],
}


@pytest.fixture(autouse=True)
def reset_fallbacks():
    """Clear the global fallback registry before and after each test."""
    clear_emitted_fallbacks()
    yield
    clear_emitted_fallbacks()


# ---------------------------------------------------------------------------
# Unit tests for individual stub builders
# ---------------------------------------------------------------------------

class TestStubDocxEmitsFallback:
    def test_stub_docx_emits_fallback_artifact(self, tmp_path: Path) -> None:
        _stub_docx_marker("run-001", tmp_path)
        fallbacks = get_emitted_fallbacks()
        assert len(fallbacks) == 1, "stub_docx must emit exactly one fallback_artifact"

    def test_stub_docx_fallback_has_correct_type(self, tmp_path: Path) -> None:
        _stub_docx_marker("run-002", tmp_path)
        fb = get_emitted_fallbacks()[0]
        assert fb["artifact_type"] == "fallback_artifact"

    def test_stub_docx_fallback_has_run_id(self, tmp_path: Path) -> None:
        _stub_docx_marker("run-003", tmp_path)
        fb = get_emitted_fallbacks()[0]
        assert fb["original_run_id"] == "run-003"

    def test_stub_docx_fallback_has_reason(self, tmp_path: Path) -> None:
        _stub_docx_marker("run-004", tmp_path)
        fb = get_emitted_fallbacks()[0]
        assert fb["fallback_reason"] == "docx_not_generated"

    def test_stub_docx_fallback_has_next_step(self, tmp_path: Path) -> None:
        _stub_docx_marker("run-005", tmp_path)
        fb = get_emitted_fallbacks()[0]
        assert fb["next_step"], "fallback_artifact must include a next_step"

    def test_stub_docx_fallback_has_unique_id(self, tmp_path: Path) -> None:
        _stub_docx_marker("run-006", tmp_path)
        fb = get_emitted_fallbacks()[0]
        assert fb["fallback_id"].startswith("fallback-")

    def test_stub_docx_without_path_still_emits_fallback(self) -> None:
        _stub_docx_marker("run-007")
        fallbacks = get_emitted_fallbacks()
        assert len(fallbacks) == 1


class TestStubRecommendationsEmitsFallback:
    def test_stub_recommendations_emits_fallback(self, tmp_path: Path) -> None:
        _stub_recommendations("run-010", tmp_path)
        fallbacks = get_emitted_fallbacks()
        assert len(fallbacks) == 1

    def test_stub_recommendations_reason(self, tmp_path: Path) -> None:
        _stub_recommendations("run-011", tmp_path)
        fb = get_emitted_fallbacks()[0]
        assert fb["fallback_reason"] == "recommendations_not_generated"

    def test_stub_recommendations_without_path(self) -> None:
        _stub_recommendations("run-012")
        fallbacks = get_emitted_fallbacks()
        assert len(fallbacks) == 1


class TestStubExecutionMetadataEmitsFallback:
    def test_stub_metadata_emits_fallback(self, tmp_path: Path) -> None:
        _stub_execution_metadata("run-020", "2026-04-24T00:00:00Z", tmp_path)
        fallbacks = get_emitted_fallbacks()
        assert len(fallbacks) == 1

    def test_stub_metadata_reason(self, tmp_path: Path) -> None:
        _stub_execution_metadata("run-021", "2026-04-24T00:00:00Z", tmp_path)
        fb = get_emitted_fallbacks()[0]
        assert fb["fallback_reason"] == "execution_metadata_not_provided"


# ---------------------------------------------------------------------------
# Integration: package_artifacts with all stubs
# ---------------------------------------------------------------------------

class TestPackageArtifactsGovernedFallbacks:
    def test_full_package_with_all_stubs_emits_fallbacks(self, tmp_path: Path) -> None:
        result = package_artifacts(
            run_id="run-100",
            structured_extraction=_MINIMAL_EXTRACTION,
            signals=_MINIMAL_SIGNALS,
            artifacts_root=tmp_path,
        )
        # Should emit fallbacks for docx, recommendations, and execution_metadata
        fallbacks = result["fallback_artifacts"]
        reasons = {fb["fallback_reason"] for fb in fallbacks}
        assert "docx_not_generated" in reasons
        assert "recommendations_not_generated" in reasons
        assert "execution_metadata_not_provided" in reasons

    def test_package_with_real_docx_no_docx_fallback(self, tmp_path: Path) -> None:
        result = package_artifacts(
            run_id="run-101",
            structured_extraction=_MINIMAL_EXTRACTION,
            signals=_MINIMAL_SIGNALS,
            artifacts_root=tmp_path,
            docx_bytes=b"real-docx-content",
        )
        reasons = {fb["fallback_reason"] for fb in result["fallback_artifacts"]}
        assert "docx_not_generated" not in reasons, (
            "No docx fallback should be emitted when real docx_bytes supplied"
        )

    def test_package_with_real_recommendations_no_recs_fallback(self, tmp_path: Path) -> None:
        result = package_artifacts(
            run_id="run-102",
            structured_extraction=_MINIMAL_EXTRACTION,
            signals=_MINIMAL_SIGNALS,
            artifacts_root=tmp_path,
            recommendations={"recommendations": [{"text": "Do X"}]},
        )
        reasons = {fb["fallback_reason"] for fb in result["fallback_artifacts"]}
        assert "recommendations_not_generated" not in reasons

    def test_fallback_artifacts_have_correct_run_id(self, tmp_path: Path) -> None:
        result = package_artifacts(
            run_id="run-103",
            structured_extraction=_MINIMAL_EXTRACTION,
            signals=_MINIMAL_SIGNALS,
            artifacts_root=tmp_path,
        )
        for fb in result["fallback_artifacts"]:
            assert fb["original_run_id"] == "run-103"

    def test_fallback_artifacts_have_schema_version(self, tmp_path: Path) -> None:
        result = package_artifacts(
            run_id="run-104",
            structured_extraction=_MINIMAL_EXTRACTION,
            signals=_MINIMAL_SIGNALS,
            artifacts_root=tmp_path,
        )
        for fb in result["fallback_artifacts"]:
            assert fb["schema_version"] == "1.0.0"

    def test_emit_fallback_artifact_direct(self) -> None:
        fb = _emit_fallback_artifact(
            run_id="run-200",
            reason="test_reason",
            message="Test fallback message",
            next_step="Fix it",
        )
        assert fb["artifact_type"] == "fallback_artifact"
        assert fb["fallback_reason"] == "test_reason"
        assert fb["schema_version"] == "1.0.0"
        assert fb["fallback_id"].startswith("fallback-")

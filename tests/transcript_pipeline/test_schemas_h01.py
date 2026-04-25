"""
H01 Schema Tests — tests/transcript_pipeline/test_schemas_h01.py

Each schema must:
- pass a valid example
- fail on missing required field
- reject unknown/additional properties
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

_SCHEMA_DIR = Path(__file__).parent.parent.parent / "contracts" / "schemas" / "transcript_pipeline"

EXPECTED_SCHEMAS = [
    "transcript_artifact",
    "normalized_transcript",
    "context_bundle",
    "meeting_minutes_artifact",
    "issue_registry_artifact",
    "structured_issue_set",
    "paper_draft_artifact",
    "review_artifact",
    "revised_draft_artifact",
    "formatted_paper_artifact",
    "release_artifact",
]


def load_schema(name: str) -> Dict[str, Any]:
    path = _SCHEMA_DIR / f"{name}.schema.json"
    assert path.exists(), f"Schema file missing: {path}"
    return json.loads(path.read_text())


def validate(schema: Dict[str, Any], instance: Dict[str, Any]) -> None:
    v = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(v.iter_errors(instance))
    if errors:
        raise ValidationError("; ".join(e.message for e in errors[:3]))


def _trace() -> Dict[str, str]:
    return {"trace_id": "a" * 32, "span_id": "b" * 16}


def _provenance() -> Dict[str, Any]:
    return {"produced_by": "test", "input_artifact_ids": []}


# ---------------------------------------------------------------------------
# All 10 schemas must exist
# ---------------------------------------------------------------------------

class TestSchemaFilesExist:
    @pytest.mark.parametrize("schema_name", EXPECTED_SCHEMAS)
    def test_schema_file_exists(self, schema_name: str) -> None:
        path = _SCHEMA_DIR / f"{schema_name}.schema.json"
        assert path.exists(), f"Schema file missing: {path}"

    @pytest.mark.parametrize("schema_name", EXPECTED_SCHEMAS)
    def test_schema_is_valid_json(self, schema_name: str) -> None:
        schema = load_schema(schema_name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema.get("additionalProperties") is False

    @pytest.mark.parametrize("schema_name", EXPECTED_SCHEMAS)
    def test_schema_requires_trace_and_provenance(self, schema_name: str) -> None:
        schema = load_schema(schema_name)
        required = schema.get("required", [])
        assert "trace" in required, f"{schema_name}: 'trace' not in required"
        assert "provenance" in required, f"{schema_name}: 'provenance' not in required"

    @pytest.mark.parametrize("schema_name", EXPECTED_SCHEMAS)
    def test_schema_requires_artifact_id_and_schema_ref(self, schema_name: str) -> None:
        schema = load_schema(schema_name)
        required = schema.get("required", [])
        assert "artifact_id" in required
        assert "schema_ref" in required
        assert "content_hash" in required


# ---------------------------------------------------------------------------
# transcript_artifact
# ---------------------------------------------------------------------------

class TestTranscriptArtifactSchema:
    def _valid(self) -> Dict[str, Any]:
        return {
            "artifact_id": "TXA-TEST001",
            "artifact_type": "transcript_artifact",
            "schema_ref": "transcript_pipeline/transcript_artifact",
            "schema_version": "1.0.0",
            "content_hash": "sha256:" + "a" * 64,
            "trace": _trace(),
            "provenance": _provenance(),
            "created_at": "2026-04-25T00:00:00+00:00",
            "source_format": "txt",
            "raw_text": "Hello world",
        }

    def test_valid_passes(self) -> None:
        schema = load_schema("transcript_artifact")
        validate(schema, self._valid())

    def test_missing_raw_text_fails(self) -> None:
        schema = load_schema("transcript_artifact")
        artifact = self._valid()
        del artifact["raw_text"]
        with pytest.raises(ValidationError):
            validate(schema, artifact)

    def test_missing_trace_fails(self) -> None:
        schema = load_schema("transcript_artifact")
        artifact = self._valid()
        del artifact["trace"]
        with pytest.raises(ValidationError):
            validate(schema, artifact)

    def test_missing_provenance_fails(self) -> None:
        schema = load_schema("transcript_artifact")
        artifact = self._valid()
        del artifact["provenance"]
        with pytest.raises(ValidationError):
            validate(schema, artifact)

    def test_unknown_field_rejected(self) -> None:
        schema = load_schema("transcript_artifact")
        artifact = self._valid()
        artifact["unknown_field"] = "should_fail"
        with pytest.raises(ValidationError):
            validate(schema, artifact)

    def test_invalid_source_format_rejected(self) -> None:
        schema = load_schema("transcript_artifact")
        artifact = self._valid()
        artifact["source_format"] = "mp3"
        with pytest.raises(ValidationError):
            validate(schema, artifact)


# ---------------------------------------------------------------------------
# meeting_minutes_artifact
# ---------------------------------------------------------------------------

class TestMeetingMinutesArtifactSchema:
    def _valid(self) -> Dict[str, Any]:
        return {
            "artifact_id": "MMA-TEST001",
            "artifact_type": "meeting_minutes_artifact",
            "schema_ref": "transcript_pipeline/meeting_minutes_artifact",
            "schema_version": "1.0.0",
            "content_hash": "sha256:" + "a" * 64,
            "trace": _trace(),
            "provenance": _provenance(),
            "created_at": "2026-04-25T00:00:00+00:00",
            "source_artifact_id": "NTX-001",
            "summary": "Team sync",
            "decisions": [],
            "action_items": [],
        }

    def test_valid_passes(self) -> None:
        schema = load_schema("meeting_minutes_artifact")
        validate(schema, self._valid())

    def test_missing_summary_fails(self) -> None:
        schema = load_schema("meeting_minutes_artifact")
        artifact = self._valid()
        del artifact["summary"]
        with pytest.raises(ValidationError):
            validate(schema, artifact)

    def test_unknown_field_rejected(self) -> None:
        schema = load_schema("meeting_minutes_artifact")
        artifact = self._valid()
        artifact["rogue_field"] = True
        with pytest.raises(ValidationError):
            validate(schema, artifact)


# ---------------------------------------------------------------------------
# review_artifact — severity ladder
# ---------------------------------------------------------------------------

class TestReviewArtifactSchema:
    def _valid(self) -> Dict[str, Any]:
        return {
            "artifact_id": "RVA-TEST001",
            "artifact_type": "review_artifact",
            "schema_ref": "transcript_pipeline/review_artifact",
            "schema_version": "1.0.0",
            "content_hash": "sha256:" + "a" * 64,
            "trace": _trace(),
            "provenance": _provenance(),
            "created_at": "2026-04-25T00:00:00+00:00",
            "reviewed_artifact_id": "PDA-001",
            "reviewed_artifact_type": "paper_draft_artifact",
            "findings": [
                {
                    "finding_id": "F-001",
                    "severity": "S2",
                    "description": "Missing citations",
                }
            ],
            "review_decision": "revise",
            "reviewer_id": "agent-red-team",
        }

    def test_valid_passes(self) -> None:
        schema = load_schema("review_artifact")
        validate(schema, self._valid())

    def test_invalid_severity_rejected(self) -> None:
        schema = load_schema("review_artifact")
        artifact = self._valid()
        artifact["findings"][0]["severity"] = "CRITICAL"
        with pytest.raises(ValidationError):
            validate(schema, artifact)

    def test_invalid_review_decision_rejected(self) -> None:
        schema = load_schema("review_artifact")
        artifact = self._valid()
        artifact["review_decision"] = "maybe"
        with pytest.raises(ValidationError):
            validate(schema, artifact)

    def test_unknown_field_in_finding_rejected(self) -> None:
        schema = load_schema("review_artifact")
        artifact = self._valid()
        artifact["findings"][0]["rogue"] = True
        with pytest.raises(ValidationError):
            validate(schema, artifact)


# ---------------------------------------------------------------------------
# release_artifact — terminal artifact
# ---------------------------------------------------------------------------

class TestReleaseArtifactSchema:
    def _valid(self) -> Dict[str, Any]:
        return {
            "artifact_id": "REL-TEST001",
            "artifact_type": "release_artifact",
            "schema_ref": "transcript_pipeline/release_artifact",
            "schema_version": "1.0.0",
            "content_hash": "sha256:" + "a" * 64,
            "trace": _trace(),
            "provenance": _provenance(),
            "created_at": "2026-04-25T00:00:00+00:00",
            "source_artifact_id": "FPA-001",
            "certification_record_id": "CERT-001",
            "release_version": "1.0.0",
            "release_status": "candidate",
            "pipeline_trace_ids": ["a" * 32],
        }

    def test_valid_passes(self) -> None:
        schema = load_schema("release_artifact")
        validate(schema, self._valid())

    def test_missing_certification_record_fails(self) -> None:
        schema = load_schema("release_artifact")
        artifact = self._valid()
        del artifact["certification_record_id"]
        with pytest.raises(ValidationError):
            validate(schema, artifact)

    def test_missing_pipeline_trace_ids_fails(self) -> None:
        schema = load_schema("release_artifact")
        artifact = self._valid()
        del artifact["pipeline_trace_ids"]
        with pytest.raises(ValidationError):
            validate(schema, artifact)

    def test_invalid_release_version_format_fails(self) -> None:
        schema = load_schema("release_artifact")
        artifact = self._valid()
        artifact["release_version"] = "v1.0"
        with pytest.raises(ValidationError):
            validate(schema, artifact)


# ---------------------------------------------------------------------------
# context_bundle — FIX-003 regression
# ---------------------------------------------------------------------------

class TestContextBundleSchema:
    """FIX-003 regression: context_bundle schema must exist and enforce structure."""

    def _valid(self) -> Dict[str, Any]:
        return {
            "artifact_id": "CTX-TEST001",
            "artifact_type": "context_bundle",
            "schema_ref": "transcript_pipeline/context_bundle",
            "schema_version": "1.0.0",
            "content_hash": "sha256:" + "a" * 64,
            "trace": _trace(),
            "provenance": _provenance(),
            "created_at": "2026-04-25T00:00:00+00:00",
            "source_artifact_id": "TXA-001",
            "context_items": [
                {
                    "item_id": "CI-001",
                    "content_type": "transcript_segment",
                    "content": "Alice: Hello.",
                }
            ],
        }

    def test_valid_passes(self) -> None:
        schema = load_schema("context_bundle")
        validate(schema, self._valid())

    def test_missing_context_items_fails(self) -> None:
        schema = load_schema("context_bundle")
        artifact = self._valid()
        del artifact["context_items"]
        with pytest.raises(ValidationError):
            validate(schema, artifact)

    def test_invalid_content_type_fails(self) -> None:
        schema = load_schema("context_bundle")
        artifact = self._valid()
        artifact["context_items"][0]["content_type"] = "unknown_type"
        with pytest.raises(ValidationError):
            validate(schema, artifact)

    def test_unknown_field_rejected(self) -> None:
        schema = load_schema("context_bundle")
        artifact = self._valid()
        artifact["rogue"] = True
        with pytest.raises(ValidationError):
            validate(schema, artifact)

"""
H02 Artifact Store Tests — tests/transcript_pipeline/test_artifact_store_h02.py

Tests:
- write + read artifact (golden path)
- invalid schema → reject (fail-closed)
- missing provenance → reject
- missing trace → reject
- content_hash mismatch → reject
- duplicate artifact_id → reject
- list_artifacts_by_type
"""
from __future__ import annotations

import copy
import uuid
from typing import Any, Dict

import pytest

from spectrum_systems.modules.runtime.artifact_store import (
    ArtifactStore,
    ArtifactStoreError,
    compute_content_hash,
)
from tests.transcript_pipeline.conftest import _make_transcript_artifact, _make_meeting_minutes_artifact


class TestArtifactStoreGoldenPath:
    def test_register_and_retrieve(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact_id = store.register_artifact(artifact)
        assert artifact_id == artifact["artifact_id"]
        retrieved = store.retrieve_artifact(artifact_id)
        assert retrieved["artifact_id"] == artifact_id

    def test_list_by_type_returns_correct_artifacts(self) -> None:
        store = ArtifactStore()
        a1 = _make_transcript_artifact()
        a2 = _make_transcript_artifact()
        mm = _make_meeting_minutes_artifact()

        store.register_artifact(a1)
        store.register_artifact(a2)
        store.register_artifact(mm)

        transcripts = store.list_artifacts_by_type("transcript_artifact")
        assert len(transcripts) == 2
        minutes = store.list_artifacts_by_type("meeting_minutes_artifact")
        assert len(minutes) == 1

    def test_artifact_count_increments(self) -> None:
        store = ArtifactStore()
        assert store.artifact_count() == 0
        store.register_artifact(_make_transcript_artifact())
        assert store.artifact_count() == 1

    def test_artifact_exists(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        assert not store.artifact_exists(artifact["artifact_id"])
        store.register_artifact(artifact)
        assert store.artifact_exists(artifact["artifact_id"])


class TestArtifactStoreFailClosed:
    def test_missing_trace_rejected(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        del artifact["trace"]
        artifact["content_hash"] = compute_content_hash(artifact)
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert "MISSING_ENVELOPE_FIELDS" in exc_info.value.reason_code

    def test_missing_provenance_rejected(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        del artifact["provenance"]
        artifact["content_hash"] = compute_content_hash(artifact)
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert "MISSING_ENVELOPE_FIELDS" in exc_info.value.reason_code

    def test_missing_provenance_input_artifact_ids_rejected(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        del artifact["provenance"]["input_artifact_ids"]
        artifact["content_hash"] = compute_content_hash(artifact)
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert exc_info.value.reason_code in (
            "MISSING_PROVENANCE_FIELDS", "SCHEMA_VALIDATION_FAILED"
        )

    def test_invalid_schema_rejected(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact["source_format"] = "unknown_format"
        artifact["content_hash"] = compute_content_hash(artifact)
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert exc_info.value.reason_code == "SCHEMA_VALIDATION_FAILED"

    def test_content_hash_mismatch_rejected(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact["content_hash"] = "sha256:" + "0" * 64
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert exc_info.value.reason_code == "CONTENT_HASH_MISMATCH"

    def test_duplicate_artifact_id_rejected(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        store.register_artifact(artifact)
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert exc_info.value.reason_code == "DUPLICATE_ARTIFACT_ID"

    def test_retrieve_nonexistent_raises(self) -> None:
        store = ArtifactStore()
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.retrieve_artifact("TXA-NONEXISTENT")
        assert exc_info.value.reason_code == "ARTIFACT_NOT_FOUND"

    def test_unknown_schema_ref_rejected(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact["schema_ref"] = "transcript_pipeline/nonexistent_type"
        artifact["content_hash"] = compute_content_hash(artifact)
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert exc_info.value.reason_code == "SCHEMA_NOT_FOUND"

    def test_missing_trace_id_in_trace_rejected(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        del artifact["trace"]["trace_id"]
        artifact["content_hash"] = compute_content_hash(artifact)
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert exc_info.value.reason_code in ("MISSING_TRACE_FIELDS", "SCHEMA_VALIDATION_FAILED")

    def test_non_dict_artifact_rejected(self) -> None:
        store = ArtifactStore()
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact("not a dict")  # type: ignore[arg-type]
        assert exc_info.value.reason_code == "INVALID_ARTIFACT_TYPE"

    def test_list_unknown_type_returns_empty(self) -> None:
        store = ArtifactStore()
        result = store.list_artifacts_by_type("nonexistent_type")
        assert result == []


class TestArtifactImmutability:
    """FIX-004 regression: deep-copy at write and read prevents post-write mutation."""

    def test_mutation_after_register_does_not_affect_stored(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        store.register_artifact(artifact)
        artifact["raw_text"] = "MUTATED AFTER WRITE"
        retrieved = store.retrieve_artifact(artifact["artifact_id"])
        assert retrieved["raw_text"] != "MUTATED AFTER WRITE"

    def test_mutation_of_retrieved_does_not_affect_stored(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        aid = store.register_artifact(artifact)
        first_copy = store.retrieve_artifact(aid)
        first_copy["raw_text"] = "MUTATED RETRIEVED COPY"
        second_copy = store.retrieve_artifact(aid)
        assert second_copy["raw_text"] != "MUTATED RETRIEVED COPY"


class TestContentHashDeterminism:
    def test_same_content_same_hash(self) -> None:
        artifact = _make_transcript_artifact()
        h1 = compute_content_hash(artifact)
        h2 = compute_content_hash(artifact)
        assert h1 == h2

    def test_different_content_different_hash(self) -> None:
        a1 = _make_transcript_artifact(raw_text="Hello")
        a2 = _make_transcript_artifact(raw_text="World")
        assert compute_content_hash(a1) != compute_content_hash(a2)

    def test_hash_prefix_is_sha256(self) -> None:
        artifact = _make_transcript_artifact()
        h = compute_content_hash(artifact)
        assert h.startswith("sha256:")
        assert len(h) == 7 + 64

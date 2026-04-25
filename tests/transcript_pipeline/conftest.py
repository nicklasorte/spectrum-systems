"""Shared fixtures for transcript pipeline tests."""
from __future__ import annotations

import uuid
from typing import Any, Dict

import pytest

from spectrum_systems.modules.runtime.artifact_store import ArtifactStore, compute_content_hash


def _trace() -> Dict[str, str]:
    return {
        "trace_id": uuid.uuid4().hex + uuid.uuid4().hex[:0],  # 32-char
        "span_id": uuid.uuid4().hex[:16],
    }


def _provenance(input_ids=None) -> Dict[str, Any]:
    return {
        "produced_by": "test_harness",
        "input_artifact_ids": input_ids or [],
        "run_id": f"run-{uuid.uuid4().hex[:8]}",
    }


def _make_transcript_artifact(**overrides) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "artifact_id": f"TXA-{uuid.uuid4().hex[:8].upper()}",
        "artifact_type": "transcript_artifact",
        "schema_ref": "transcript_pipeline/transcript_artifact",
        "schema_version": "1.0.0",
        "trace": _trace(),
        "provenance": _provenance(),
        "created_at": "2026-04-25T00:00:00+00:00",
        "source_format": "txt",
        "raw_text": "Alice: Hello.\nBob: Hi.",
    }
    base.update(overrides)
    base["content_hash"] = compute_content_hash(base)
    return base


def _make_meeting_minutes_artifact(**overrides) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "artifact_id": f"MMA-{uuid.uuid4().hex[:8].upper()}",
        "artifact_type": "meeting_minutes_artifact",
        "schema_ref": "transcript_pipeline/meeting_minutes_artifact",
        "schema_version": "1.0.0",
        "trace": _trace(),
        "provenance": _provenance(),
        "created_at": "2026-04-25T00:00:00+00:00",
        "source_artifact_id": "NTX-TEST001",
        "summary": "Team aligned on Q2 goals.",
        "decisions": [
            {
                "decision_id": "D-001",
                "description": "Adopt new schema format",
                "rationale": "Improves machine readability and schema compliance.",
            }
        ],
        "action_items": [
            {"action_id": "AI-001", "description": "Draft schema proposal"}
        ],
    }
    base.update(overrides)
    base["content_hash"] = compute_content_hash(base)
    return base


@pytest.fixture
def store() -> ArtifactStore:
    return ArtifactStore()


@pytest.fixture
def valid_transcript_artifact() -> Dict[str, Any]:
    return _make_transcript_artifact()


@pytest.fixture
def valid_meeting_minutes_artifact() -> Dict[str, Any]:
    return _make_meeting_minutes_artifact()

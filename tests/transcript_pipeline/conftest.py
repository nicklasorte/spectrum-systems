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
    source_ref = {
        "source_turn_id": "T-0001",
        "source_segment_id": "SEG-0001",
        "line_index": 0,
    }
    base: Dict[str, Any] = {
        "artifact_id": f"MMA-{uuid.uuid4().hex[:8].upper()}",
        "artifact_type": "meeting_minutes_artifact",
        "schema_ref": "transcript_pipeline/meeting_minutes_artifact",
        "schema_version": "2.0.0",
        "trace": _trace(),
        "provenance": _provenance(),
        "created_at": "2026-04-25T00:00:00+00:00",
        "source_artifact_ids": ["TXA-TEST001", "CTX-TEST001"],
        "source_context_bundle_id": "CTX-TEST001",
        "summary": "Team aligned on Q2 goals.",
        "attendees": ["Alice", "Bob"],
        "agenda_items": [
            {
                "agenda_item_id": "AGI-0001",
                "title": "Q2 goals",
                "source_refs": [source_ref],
            }
        ],
        "decisions": [
            {
                "decision_id": "DEC-0001",
                "description": "Adopt new schema format",
                "rationale": "Improves machine readability and schema compliance.",
                "source_refs": [source_ref],
            }
        ],
        "action_items": [
            {
                "action_id": "ACT-0001",
                "description": "Draft schema proposal",
                "assignee": "Alice",
                "due_date": "2026-05-31",
                "source_refs": [source_ref],
            }
        ],
        "source_coverage": {
            "total_turns": 1,
            "referenced_turns": 1,
            "referenced_segments": 1,
            "coverage_ratio": 1.0,
        },
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

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
        "schema_version": "1.1.0",
        "trace": _trace(),
        "provenance": _provenance(["TXA-TEST001", "CTX-TEST001", "GTE-TEST001"]),
        "created_at": "2026-04-25T00:00:00+00:00",
        "source_context_bundle_id": "CTX-TEST001",
        "summary": "Team aligned on Q2 goals.",
        "agenda_items": [],
        "meeting_outcomes": [
            {
                "outcome_id": "OUT-001",
                "description": "We agreed to adopt new schema format.",
                "source_refs": [
                    {
                        "source_turn_id": "T-0001",
                        "source_segment_id": "SEG-0001",
                        "line_index": 0,
                    }
                ],
            }
        ],
        "action_items": [
            {
                "action_id": "ACT-001",
                "description": "Action: @alex drafts schema by 2026-05-01.",
                "assignee": "alex",
                "due_date": "2026-05-01",
                "source_refs": [
                    {
                        "source_turn_id": "T-0002",
                        "source_segment_id": "SEG-0002",
                        "line_index": 1,
                    }
                ],
            }
        ],
        "attendees": ["Alex", "Sam"],
        "source_coverage": {
            "covered_turn_ids": ["T-0001", "T-0002"],
            "covered_segment_ids": ["SEG-0001", "SEG-0002"],
            "total_transcript_turns": 2,
            "covered_transcript_turns": 2,
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

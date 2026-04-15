from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_wpg31_meeting_artifact_ingested_as_governed_input() -> None:
    payload = _payload()
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id=payload["run_id"],
        trace_id=payload["trace_id"],
        meeting_artifact=payload["meeting_artifact"],
    )
    meeting = bundle["artifact_chain"]["meeting_artifact"]
    assert meeting["artifact_type"] == "meeting_artifact"
    assert meeting["outputs"]["topic"] == "Workflow loop validation"


def test_wpg31_invalid_meeting_artifact_blocks() -> None:
    payload = _payload()
    bad_meeting = dict(payload["meeting_artifact"])
    bad_meeting.pop("participants", None)
    with pytest.raises(Exception):
        run_wpg_pipeline(payload["transcript"], run_id="bad-meeting", trace_id="bad-meeting", meeting_artifact=bad_meeting)

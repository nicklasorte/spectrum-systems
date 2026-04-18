from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline
from tests.wpg_context_helpers import build_complete_context_bundle

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_crm07_comment_ingestion_accepts_governed_comments() -> None:
    payload = _payload()
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id="crm-ingest",
        trace_id="crm-ingest",
        meeting_artifact=payload["meeting_artifact"],
        comment_artifact=payload["comment_artifact"],
        context_bundle_artifact=build_complete_context_bundle(trace_id="crm-ingest", run_id="crm-ingest"),
    )
    comments = bundle["artifact_chain"]["comment_artifact"]
    assert comments["artifact_type"] == "comment_artifact"
    assert len(comments["outputs"]["comments"]) == 2


def test_crm07_invalid_comment_blocks() -> None:
    payload = _payload()
    invalid = {"comments": [{"comment_id": "c-1", "text": "", "severity": "normal", "critical": False}]}
    with pytest.raises(Exception):
        run_wpg_pipeline(
            payload["transcript"],
            run_id="crm-invalid",
            trace_id="crm-invalid",
            meeting_artifact=payload["meeting_artifact"],
            comment_artifact=invalid,
            context_bundle_artifact=build_complete_context_bundle(trace_id="crm-invalid", run_id="crm-invalid"),
        )

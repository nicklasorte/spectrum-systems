from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline
from tests.wpg_context_helpers import build_complete_context_bundle

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def test_crm08_resolution_matrix_is_valid_and_structured() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id="crm-matrix",
        trace_id="crm-matrix",
        meeting_artifact=payload["meeting_artifact"],
        comment_artifact=payload["comment_artifact"],
        context_bundle_artifact=build_complete_context_bundle(trace_id="crm-matrix", run_id="crm-matrix"),
    )
    matrix = bundle["artifact_chain"]["comment_resolution_matrix"]
    assert matrix["artifact_type"] == "comment_resolution_matrix"
    assert matrix["entries"]

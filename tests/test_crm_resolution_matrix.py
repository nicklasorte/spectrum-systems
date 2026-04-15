from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def test_crm08_resolution_matrix_is_valid_and_structured() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id="crm-matrix",
        trace_id="crm-matrix",
        meeting_artifact=payload["meeting_artifact"],
        comment_artifact=payload["comment_artifact"],
    )
    matrix = bundle["artifact_chain"]["comment_resolution_matrix"]
    assert matrix["artifact_type"] == "comment_resolution_matrix"
    assert matrix["entries"]

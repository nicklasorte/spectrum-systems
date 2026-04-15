from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def test_crm12_disposition_tracking_explicit_state() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id="crm-disposition",
        trace_id="crm-disposition",
        meeting_artifact=payload["meeting_artifact"],
        comment_artifact=payload["comment_artifact"],
    )
    disposition = bundle["artifact_chain"]["comment_disposition_record"]
    assert "resolved" in disposition["outputs"]["state_counts"]

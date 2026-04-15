from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline

FIXTURE = Path("tests/fixtures/wpg/sample_workflow_loop_input.json")


def test_crm09_comment_mapping_traceability_present() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle = run_wpg_pipeline(
        payload["transcript"],
        run_id="crm-map",
        trace_id="crm-map",
        meeting_artifact=payload["meeting_artifact"],
        comment_artifact=payload["comment_artifact"],
    )
    mapping = bundle["artifact_chain"]["comment_mapping_record"]
    assert mapping["outputs"]["mappings"]
    assert mapping["outputs"]["critical_unmapped"] >= 0
